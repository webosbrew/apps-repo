#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
from os import path
from repogen import apppage, apidata
from repogen.common import list_packages

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)
args = parser.parse_args()

packages = list_packages(args.input_dir)
apidata.generate(packages, path.join(args.output_dir, 'api'))
apppage.generate(packages, path.join(args.output_dir, 'apps'))
