# PAG Greenspace Network Travel

Code accompanying the manuscript

> **Pedestrian and Driving Network Distances to Greenspace for Lower Super Output Areas in England**

## Overview

This repository contains the code used to calculate network-based travel times between Lower Super Output Areas (LSOAs) and publicly accessible greenspaces in England.

The repository accompanies the associated publication and is intended to provide transparency and reproducibility of the methods described in the paper.

## Repository structure

```
src/
scripts/
examples/
```

## Requirements

Python 3.12+

Install with

```bash
pip install -e .
```

or

```bash
conda env create -f environment.yml
```

## Running

Example:

```bash
python scripts/run_analysis.py
```

## Data

The datasets used in the publication are described in the manuscript.

Large datasets are not included in this repository.

## Citation

If you use this software, please cite the accompanying publication.

## License

MIT License.