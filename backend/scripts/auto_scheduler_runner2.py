from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import subprocess
import time

# 定义需要调用的程序路径
program_30min = "python3 run_probabilistic_scheduler.py"  # 每30分钟调用的程序
program_2hour = "python3 run_probabilistic_detective_scheduler.py"  # 每2小时调用的程序

# 定义调用函数
def call_program_30min():
    print("正在调用程序1...")
    subprocess.run(program_30min, shell=True)

def call_program_2hour():
    print("正在调用程序2...")
    subprocess.run(program_2hour, shell=True)

# 处理调度的事件（任务执行完后打印日志）
def job_listener(event):
    if event.exception:
        print(f"任务 {event.job_id} 执行失败！")
    else:
        print(f"任务 {event.job_id} 执行成功！")

# 创建调度器
scheduler = BlockingScheduler()
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# 每30分钟执行一次程序1
scheduler.add_job(call_program_30min, 'interval', minutes=30, id='job_30min')

# 每2小时执行一次程序2
scheduler.add_job(call_program_2hour, 'interval', hours=2, id='job_2hour')

# 启动调度器
scheduler.start()