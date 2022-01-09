#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from os import path
from repogen import apppage, apidata
from repogen.common import list_packages

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)

parser.add_argument('-A', '--no-gen-api', dest='gen_api', action='store_false')
parser.add_argument('-D', '--no-gen-details', dest='gen_details', action='store_false')
parser.add_argument('-L', '--no-gen-list', dest='gen_list', action='store_false')

parser.set_defaults(gen_api=True, gen_details=True, gen_list=True)

args = parser.parse_args()

packages = list_packages(args.input_dir)

if args.gen_api:
    apidata.generate(packages, path.join(args.output_dir, 'api'))

apppage.generate(packages, path.join(args.output_dir, 'apps'), gen_details=args.gen_details, gen_list=args.gen_list)
