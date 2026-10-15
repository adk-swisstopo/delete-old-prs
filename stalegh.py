#!/usr/bin/env python3

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

	def GetAge(self):
		now = datetime.datetime.now(tz=pytz.UTC)
		return now - self.GetLastCommitDate()

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

def GetAllRepos(ghc, organizations=None, repos=None):
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

def GetRepos(*args, archived=False, **kwargs):
	for repo in GetAllRepos(*args, **kwargs):
		if not archived and repo.archived:
			Log(f'Repo is archived, skipping: https://github.com/{repo.full_name}')
			continue
		yield repo

def ListBranches(ghc, organizations=None, repos=None):
	for repo in GetRepos(ghc, organizations=organizations, repos=repos):
		for branch in repo.get_branches():
			yield Branch(repo=repo, branch=branch)

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

def GetGHClient():
	return github.Github(auth=github.Auth.Token(FindToken()))

def Log(message):
	print(message, file=sys.stderr)
