#!/usr/bin/env python3

import datetime
import github
import os
import pytz
import sys
import yaml

class PullRequest(object):
	def __init__(self, organization, repo, pr):
		self._organization = organization
		self._repo = repo
		# last_modified_datetime comes from last-modified header
		# it seems to change spuriously
		# it is not available on get_pulls(), only on get_pull()
		# updated_at seems to track is updated less often but it seems to track what we want and it available on get_pulls()
		self._pr = pr

	def __str__(self):
		return f'{self.repo_path}/pull/{self._pr.number}'

	@property
	def repo_path(self):
		return f'https://github.com/{self._organization.login}/{self._repo.name}'

	@property
	def updated_at(self):
		return self._pr.updated_at

	def is_open(self):
		return self._pr.state == 'open'

	def close(self, comment):
		# TODO: error checking?
		self._pr.create_comment(comment)
		self._pr.edit(state='closed')

def ListPrs(ghc, org_names):
	for org_name in org_names:
		org = ghc.get_organization(org_name)
		for repo in org.get_repos():
			for pr in repo.get_pulls():
				yield PullRequest(organization=org, repo=repo, pr=pr)

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
	# TODO: parameterise ~everything
	DEFAULT_ORGS=('geoadmin', 'swissgeo')
	now = datetime.datetime.now(tz=pytz.UTC)
	closeable_dt = now - datetime.timedelta(days=90)
	ghc = github.Github(auth=github.Auth.Token(FindToken()))
	prs_to_close = set()
	prs_count = 0
	for pr in ListPrs(ghc, DEFAULT_ORGS):
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
	# TODO: actually close:
	#	pr.close('This PR has not been updated in a long time and is now being closed. Feel free to reopen if needed.')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
