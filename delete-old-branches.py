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

class ProgressTracker(object):
	def __init__(self, output=sys.stderr, newlines=False):
		self.current = 0
		self.total = 0
		self.output = output
		self.newlines = newlines

	def Report(self, message, last=False):
		full_message = f'{self.current}/{self.total} {message}'
		try:
			term_width = os.get_terminal_size().columns
		except OSError:
			term_width = 80
		if self.newlines:
			full_message = f'{full_message}\n'
		else:
			full_message = f'\r{full_message}'
		written = self.output.write(full_message)
		if not self.newlines:
			self.output.write(' ' * (term_width - written - 1))
		if last and not self.newlines:
			self.output.write('\n')
		self.output.flush()

def main(argv):
	parser = argparse.ArgumentParser(
		prog='close-old-prs',
		description='Close GitHub PRs that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-k', '--branches_to_keep', action='append', default=['master', 'main', 'develop'])
	parser.add_argument('-n', '--dry-run', action=argparse.BooleanOptionalAction, default=True)
	parser.add_argument('-l', '--new-lines', action=argparse.BooleanOptionalAction, default=False)
	args = parser.parse_args(argv[1:])
	if args.days < 7:
		print('Automatically deleting branches that are only {args.days} days old sounds dangerous. Not proceeding.', file=sys.stderr)
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	stale_cutoff = now - datetime.timedelta(days=args.days)
	ghc = github.Github(auth=github.Auth.Token(FindToken()))

	progress = ProgressTracker(newlines=args.new_lines)
	branches_to_delete = set()
	for branch in ListAllBranches(ghc, organizations=args.organizations, repos=args.repos):
		progress.total += 1
		if branch.IsDefault():
			progress.Report(f'branches to delete: {branch} skipped: default branch')
			continue
		if branch.name in args.branches_to_keep:
			progress.Report(f'branches to delete: {branch} skipped: in list of branches to keep')
			continue
		if branch.ModifiedSince(stale_cutoff):
			progress.Report(f'branches to delete: {branch} skipped: has recent modification')
			continue
		if branch.HasOpenPr():
			progress.Report(f'branches to delete: {branch} skipped: has associated PR')
			continue
		branches_to_delete.add(branch)
		progress.current += 1
		progress.Report(f'branches to delete: {branch} eligible for deletion')
	progress.Report(f'branches to delete. Done scanning branches.', last=True)
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	progress = ProgressTracker(newlines=args.new_lines)
	progress.total = len(branches_to_delete)
	for branch in branches_to_delete:
		message = f'branches deleted: {branch}'
		if args.dry_run:
			message += ' DRY RUN'
		else:
			branch.Delete()
		progress.current += 1
		progress.Report(message)
	message = 'branches deleted.'
	if args.dry_run:
		message += ' DRY RUN'
	progress.Report(message, last=True)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
