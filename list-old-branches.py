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

	def GetAge(self):
		now = datetime.datetime.now(tz=pytz.UTC)
		return now - self.GetLastCommitDate()

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

def LogScanProgress(total, message):
	Log(f'{total} branches found. {message}')

def main(argv):
	parser = argparse.ArgumentParser(
		prog='close-old-prs',
		description='Close GitHub PRs that were not updated for a long time.')
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-k', '--branches_to_keep', action='append', default=['master', 'main', 'develop'])
	parser.add_argument('-n', '--dry-run', action=argparse.BooleanOptionalAction, default=True)
	args = parser.parse_args(argv[1:])
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	ghc = github.Github(auth=github.Auth.Token(FindToken()))

	branches_total = 0
	for branch in ListAllBranches(ghc, organizations=args.organizations, repos=args.repos):
		branches_total += 1
		if branch.IsDefault():
			LogScanProgress(branches_total, f'Skipped: default branch: {branch}')
			continue
		if branch.name in args.branches_to_keep:
			LogScanProgress(branches_total, f'Skipped: in list of branches to keep: {branch}')
			continue
		print(f'{branch} {branch.GetAge().days} days old')
	LogScanProgress(branches_total, 'Done scanning branches.')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
