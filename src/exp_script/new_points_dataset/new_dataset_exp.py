from exp_script.bias.point_set import generate_same_number_with_sample
from exp_script.statistic_file import statistic
from exp_script.tran_dataset import tran_dataset_cracksql, tran_model_dataset, tran_dataset
from exp_script.verify_res import process_file

sql_number = 100

tool = 'qwen'
output_path1 = f'your path to store sql sets1'
points1_path = f'your path to qwen_points.json'
generate_same_number_with_sample(sql_number, output_path1, points1_path)

# verify result
tran_dataset(output_path1, 'new_pointws', True)

if output_path1.endswith('exp_res.json') or output_path1.endswith('exp_res_flt.json'):
    res1_path = output_path1
else:
    res1_path = f'{output_path1.removesuffix(".json")}_exp_res.json'

process_file(res1_path, multi_mode=True, tran_flag=False)

statistic(res1_path)
