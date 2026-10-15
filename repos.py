#!/usr/bin/env python3
# TODO: dedupe with branches.py and prs.py

import argparse
import datetime
import pytz
import stalegh
import sys

def LogScanProgress(current, total, message):
	stalegh.Log(f'{current}/{total} eligible repos. {message}')

def main(argv):
	parser = argparse.ArgumentParser(
		prog='prs',
		description='List or archive GitHub repos that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-a', '--action', default='print')
	args = parser.parse_args(argv[1:])
	if args.action not in ('print', 'archive'):
		print(f'Invalid action: {args.action} must be "print" or "archive".')
		return -1
	if args.action == 'archive' and args.days < 7:
		print('Automatically archiving repos that are only {args.days} days old sounds dangerous. Not proceeding.', file=sys.stderr)
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	stale_cutoff = now - datetime.timedelta(days=args.days)
	ghc = stalegh.GetGHClient()

	repos_to_process = set()
	repos_total = 0
	for repo in stalegh.GetRepos(ghc, organizations=args.organizations, repos=args.repos):
		repos_total += 1
		if repo.updated_at > stale_cutoff:
			LogScanProgress(len(repos_to_process), repos_total, f'Skipped: has recent modification: {repo}')
			continue
		repos_to_process.add(repo)
		LogScanProgress(len(repos_to_process), repos_total, f'Eligible for archival: {repo}')
	LogScanProgress(len(repos_to_process), repos_total, 'Done scanning repos.')
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	i = 0
	for repo in repos_to_process:
		if args.action == 'archive':
			raise NotImplementedError
		elif args.action == 'print':
			name = f'https://github.com/{repo.full_name}'
			age = now - repo.updated_at
			print(f'{name} last updated {age.days} days ago')
		i += 1
		stalegh.Log(f'{i}/{len(repos_to_process)} repos processed: {repo}')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
