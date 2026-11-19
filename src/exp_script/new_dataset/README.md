## New Dataset

We add job as new dataset for evaluation. To reproduce our experiment results, please follow the instructions below.

1. Download the job dataset and put it in the `data` folder you have specified in `config.yaml`. The dataset can be downloaded from [here](https://zenodo.org/records/19741455?preview=1&token=eyJhbGciOiJIUzUxMiJ9.eyJpZCI6IjBhOTU1MGM3LTdjZWUtNDc5OC1hYmQ1LTU0M2M3YTM3MjJmNSIsImRhdGEiOnt9LCJyYW5kb20iOiJhYjRlOWUwMDQ2MWYwY2QyZjcwZTEzYmQ2NzdhNWZiZCJ9.vq6YLYM8r89Wfw4ujKFEIh6fqakNVEANMy68W2dOhDHr3CuM7F1xXdi-DxsaX67FeNeBEwpCW4nvMSPygYxzaQ).

2. Build the dataset with (or if you have already built the dataset, you can skip this step):

```bash
python -m exp.script.new_dataset.db_builder
```

2. Revising the SQL path used in the Generator (src/sql_gen/generator/generate_pipeline.py load_no_point_sqls) change the `f'{src_dialect}_{tgt_dialect}_marked.json'` into `f'{src_dialect}_{tgt_dialect}_job_marked.json'`.

3. Run the generation script to generate the SQLs for the job dataset. 

```bash
cd src
python -m exp.script.new_dataset.new_dataset_exp
```