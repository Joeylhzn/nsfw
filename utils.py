# -*- coding: utf-8 -*-
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description='nsfw')

    parser.add_argument(dest='filenames', metavar='filename', nargs='*')

    parser.add_argument('-S', '--search', metavar='pattern', required=True,
                        dest='patterns', action='append',
                        help='text pattern to search for')

    parser.add_argument('-v', dest='verbose', action='store_true',
                        help='verbose mode')

    parser.add_argument('-o', dest='outfile', action='store',
                        help='output file')
    return parser.parse_args()