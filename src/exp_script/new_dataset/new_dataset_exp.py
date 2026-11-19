from exp_script.new_dataset.gen import generate_same_scale_with_all_job
from exp_script.statistic_file import statistic
from exp_script.translate_scripts.tran_dataset import tran_dataset
from exp_script.verify_res import process_file

set_number = 100

output_path = 'your path to store sql sets1'
generate_same_scale_with_all_job(set_number, output_path)

tran_dataset(output_path, 'job', True)

# verify result
if output_path.endswith('exp_res.json') or output_path.endswith('exp_res_flt.json'):
    res1_path = output_path
else:
    res1_path = f'{output_path.removesuffix(".json")}_exp_res.json'

process_file(res1_path, multi_mode=True, tran_flag=False)

statistic(res1_path)
