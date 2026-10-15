#!/usr/bin/env python3
# TODO: deduple branches.py and prs.py

import argparse
import datetime
import pytz
import stalegh
import sys

def LogScanProgress(current, total, message):
	stalegh.Log(f'{current}/{total} eligible PRs. {message}')

def main(argv):
	parser = argparse.ArgumentParser(
		prog='prs',
		description='List or close GitHub PRs that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-a', '--action', default='print')
	args = parser.parse_args(argv[1:])
	if args.action not in ('print', 'delete'):
		print(f'Invalid action: {args.action} must be "print" or "delete".')
		return -1
	if args.action == 'delete' and args.days < 7:
		print('Automatically closing PRs that are only {args.days} days old sounds dangerous. Not proceeding.', file=sys.stderr)
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	stale_cutoff = now - datetime.timedelta(days=args.days)
	ghc = stalegh.GetGHClient()

	prs_to_process = set()
	prs_total = 0
	for pr in stalegh.ListPrs(ghc, organizations=args.organizations, repos=args.repos):
		prs_total += 1
		if not pr.is_open():
			LogScanProgress(len(prs_to_process), prs_total, f'Skipped: PR is not open: {pr}')
			continue
		if pr.ModifiedSince(stale_cutoff):
			LogScanProgress(len(prs_to_process), prs_total, f'Skipped: has recent modification: {pr}')
			continue
		prs_to_process.add(pr)
		LogScanProgress(len(prs_to_process), prs_total, f'Eligible for closure: {pr}')
	LogScanProgress(len(prs_to_process), prs_total, 'Done scanning PRs.')
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	i = 0
	for pr in prs_to_process:
		if args.action == 'delete':
			pr.close()
		elif args.action == 'print':
			print(f'{pr} last updated {pr.GetAge().days} days ago')
		i += 1
		stalegh.Log(f'{i}/{len(prs_to_process)} PRs processed: {pr}')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
