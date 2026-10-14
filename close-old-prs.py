#!/usr/bin/env python3

import argparse
import datetime
import github
import os
import pytz
import sys
import yaml

class PullRequest(object):
	def __init__(self, repo, pr):
		self._repo = repo
		self._pr = pr

	def __str__(self):
		return f'{self.repo_path}/pull/{self._pr.number}'

	@property
	def repo_path(self):
		return f'https://github.com/{self._repo.full_name}'

	@property
	def repo_name(self):
		return self._repo.name

	@property
	def updated_at(self):
		# Another interesting field is last_modified_datetime, which
		# comes from the last-modified header of the response. However
		# it seems to change rather spuriously. That is, old PRs that
		# have had no obvious changes often have a quite recent
		# last_modified_datetime field. Furthermore, that field is only
		# populated when the PR is retrieved invidually, not via an
		# operation that retrieves multiple PRs.
		# In comparison, updated_at seems to have the desired semantic
		# and does not require an API call for each PR.
		return self._pr.updated_at

	def is_open(self):
		return self._pr.state == 'open'

	def close(self, comment):
		# TODO: error checking?
		self._pr.create_comment(comment)
		self._pr.edit(state='closed')

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

def ListPrs(ghc, organizations=None, repos=None):
	for repo in GetRepos(ghc, organizations=organizations, repos=repos):
		for pr in repo.get_pulls():
			yield PullRequest(repo=repo, pr=pr)

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

def main(argv):
	parser = argparse.ArgumentParser(
		prog='close-old-prs',
		description='Close GitHub PRs that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-n', '--dry-run', action=argparse.BooleanOptionalAction, default=True)
	args = parser.parse_args(argv[1:])
	if args.days < 7:
		print('Automatically closing PRs that are only {args.days} days old sounds dangerous. Not proceeding.')
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	closeable_dt = now - datetime.timedelta(days=args.days)
	ghc = github.Github(auth=github.Auth.Token(FindToken()))
	prs_to_close = set()
	prs_count = 0
	for pr in ListPrs(ghc, organizations=args.organizations, repos=args.repos):
		prs_count += 1
		if not pr.is_open():
			print(f'{pr}: skipped: not state "open"', file=sys.stderr)
			continue
		if pr.updated_at > closeable_dt:
			age = now - pr.updated_at
			print(f'{pr}: skipped: only {age.days} days old', file=sys.stderr)
			continue
		print(f'{pr}: can be closed')
		prs_to_close.add(pr)
	print(f'{len(prs_to_close)}/{prs_count} PRs can be closed', file=sys.stderr)
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	#	skip PRs that have the no-auto-close label
	for pr in prs_to_close:
		if args.dry_run:
			print(f'dry run: not closing {pr}')
		else:
			# TODO: actually close:
			#	pr.close('This PR has not been updated in a long time and is now being closed. Feel free to reopen if needed.')
			print(f'actually closing {pr} (not really)')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
