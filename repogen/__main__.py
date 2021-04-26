import argparse
from os import path

from repogen import apppage, jsondata

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)
args = parser.parse_args()

jsondata.generate(args.input_dir, path.join(args.output_dir, 'api'))
apppage.generate(args.input_dir, path.join(args.output_dir, 'apps'))
