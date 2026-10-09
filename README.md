# c0mpiled_hackathon_2026
Lawn mowing extension to use AI and Satellite imagery to estimate the cost of mowing a lawn fully autonomously. Hook it up to your lawn mowing company now!

## Setup (EC2 or any Linux/Mac machine)

```bash
mamba env create -f environment.yml   # or: conda env create -f environment.yml
conda activate lawn
python get_lawn_data.py               # writes ./data/
```

`get_lawn_data.py` downloads NAIP imagery, Overture building footprints, and (optionally)
Chesapeake 1 m land cover and county parcels for a small State College bounding box,
all reprojected to EPSG:26918. Run `python get_lawn_data.py -h` for options.
