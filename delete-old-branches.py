#!/usr/bin/env python3

import argparse
import datetime
import github
import os
import pytz
import sys
import yaml

class Branch(object):
	def __init__(self, repo, branch):
		self._repo = repo
		self._branch = branch

	def __str__(self):
		return f'https://github.com/{self._repo.full_name}/tree/{self.name}'

	@property
	def updated_at(self):
		return self._branch.commit.stats.last_modified
	
	@property
	def name(self):
		return self._branch.name

	def GetLastCommitDate(self):
		return datetime.datetime.fromisoformat(
			self._branch.commit.raw_data['commit']['author']['date'])

	def Delete(self):
		ref = self._repo.get_git_ref(f'heads/{self.name}')
		ref.delete()

	def IsDefault(self):
		return self.name == self._repo.default_branch

	def HasOpenPr(self):
		for pr in self._branch.commit.get_pulls():
			if pr.state == 'open':
				return True

	def ModifiedSince(self, stale_cutoff):
		return self.GetLastCommitDate() > stale_cutoff
		

def GetRepos(ghc, organizations=None, repos=None):
	if not organizations:
		for repo in repos:
			yield ghc.get_repo(repo)
	else:
		for org_name in organizations:
			org = ghc.get_organization(org_name)
			for repo in org.get_repos():
				if repos and repo.name not in repos:
					continue
				yield repo

def ListAllBranches(ghc, organizations=None, repos=None):
	for repo in GetRepos(ghc, organizations=organizations, repos=repos):
		if repo.archived:
			Log(f'Repo is archived, skipping: https://github.com/{repo.full_name}')
			continue
		for branch in repo.get_branches():
			yield Branch(repo=repo, branch=branch)

def FindToken():
	token = os.getenv('GITHUB_TOKEN')
	if token:
		return token
	return GetTockenFromGHConfig()

def GetTockenFromGHConfig():
	GH_HOST_CONFIG = os.path.join(os.getenv('HOME'), '.config/gh/hosts.yml')
	with open(GH_HOST_CONFIG, mode='r') as f:
		config = yaml.safe_load(f)
		return config['github.com']['oauth_token']

def Log(message):
	print(message, file=sys.stderr)

def LogScanProgress(current, total, message):
	Log(f'{current}/{total} branches to delete. {message}')

def main(argv):
	parser = argparse.ArgumentParser(
		prog='close-old-prs',
		description='Close GitHub PRs that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-k', '--branches_to_keep', action='append', default=['master', 'main', 'develop'])
	parser.add_argument('-n', '--dry-run', action=argparse.BooleanOptionalAction, default=True)
	args = parser.parse_args(argv[1:])
	if args.days < 7:
		print('Automatically deleting branches that are only {args.days} days old sounds dangerous. Not proceeding.', file=sys.stderr)
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	stale_cutoff = now - datetime.timedelta(days=args.days)
	ghc = github.Github(auth=github.Auth.Token(FindToken()))

	branches_to_delete = set()
	branches_total = 0
	for branch in ListAllBranches(ghc, organizations=args.organizations, repos=args.repos):
		branches_total += 1
		if branch.IsDefault():
			LogScanProgress(len(branches_to_delete), branches_total, f'Skipped: default branch: {branch}')
			continue
		if branch.name in args.branches_to_keep:
			LogScanProgress(len(branches_to_delete), branches_total, f'Skipped: in list of branches to keep: {branch}')
			continue
		if branch.HasOpenPr():
			LogScanProgress(len(branches_to_delete), branches_total, f'Skipped: has associated PR: {branch}')
			continue
		if branch.ModifiedSince(stale_cutoff):
			LogScanProgress(len(branches_to_delete), branches_total, f'Skipped: has recent modification: {branch}')
			continue
		branches_to_delete.add(branch)
		LogScanProgress(len(branches_to_delete), branches_total, f'Eligible for deletion: {branch}')
	LogScanProgress(len(branches_to_delete), branches_total, 'Done scanning branches.')
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	deleted_count = 0
	for branch in branches_to_delete:
		dryrun_trailer = ''
		if args.dry_run:
			dryrun_trailer = ' DRY RUN'
		else:
			branch.Delete()
		deleted_count += 1
		Log(f'{deleted_count}/{len(branches_to_delete)} branches deleted: {branch} {dryrun_trailer}')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
