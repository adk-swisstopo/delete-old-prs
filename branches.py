#!/usr/bin/env python3

import argparse
import datetime
import pytz
import stalegh
import sys

def LogScanProgress(current, total, message):
	stalegh.Log(f'{current}/{total} eligible branches. {message}')

def main(argv):
	parser = argparse.ArgumentParser(
		prog='branches',
		description='List or delete GitHub branches that were not updated for a long time.')
	parser.add_argument('-d', '--days', type=int, default=90)
	parser.add_argument('-O', '--organizations', action='append')
	parser.add_argument('-r', '--repos', action='append')
	parser.add_argument('-k', '--branches_to_keep', action='append', default=['master', 'main', 'develop'])
	parser.add_argument('-a', '--action', default='print')
	args = parser.parse_args(argv[1:])
	if args.action not in ('print', 'delete'):
		print(f'Invalid action: {args.action} must be "print" or "delete".')
		return -1
	if args.action == 'delete' and args.days < 7:
		print('Automatically deleting branches that are only {args.days} days old sounds dangerous. Not proceeding.', file=sys.stderr)
		return -1
	if not args.repos and not args.organizations:
		args.organizations = ('geoadmin', 'swissgeo')

	now = datetime.datetime.now(tz=pytz.UTC)
	stale_cutoff = now - datetime.timedelta(days=args.days)
	ghc = stalegh.GetGHClient()

	branches_to_process = set()
	branches_total = 0
	for branch in stalegh.ListBranches(ghc, organizations=args.organizations, repos=args.repos):
		branches_total += 1
		if branch.IsDefault():
			LogScanProgress(len(branches_to_process), branches_total, f'Skipped: default branch: {branch}')
			continue
		if branch.name in args.branches_to_keep:
			LogScanProgress(len(branches_to_process), branches_total, f'Skipped: in list of branches to keep: {branch}')
			continue
		if branch.HasOpenPr():
			LogScanProgress(len(branches_to_process), branches_total, f'Skipped: has associated PR: {branch}')
			continue
		if branch.ModifiedSince(stale_cutoff):
			LogScanProgress(len(branches_to_process), branches_total, f'Skipped: has recent modification: {branch}')
			continue
		branches_to_process.add(branch)
		LogScanProgress(len(branches_to_process), branches_total, f'Eligible for deletion: {branch}')
	LogScanProgress(len(branches_to_process), branches_total, 'Done scanning branches.')
	# TODO: safety checks
	#       don't close more than X% total
	#       don't close more than Y% per repo that have more than Z PRs open
	i = 0
	for branch in branches_to_process:
		if args.action == 'delete':
			branch.Delete()
		elif args.action == 'print':
			print(f'{branch} last updated {branch.GetAge().days} days ago')
		i += 1
		stalegh.Log(f'{i}/{len(branches_to_process)} branches processed: {branch}')

if __name__ == '__main__':
    sys.exit(main(sys.argv))
