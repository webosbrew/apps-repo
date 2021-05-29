import argparse
from os import path

from repogen import apppage, apidata

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input-dir', required=True)
parser.add_argument('-o', '--output-dir', required=True)
args = parser.parse_args()

apidata.generate(args.input_dir, path.join(args.output_dir, 'api'))
apppage.generate(args.input_dir, path.join(args.output_dir, 'apps'))
