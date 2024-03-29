
import os
import sys
import subprocess
import shutil
import traceback
import platform
import threading
import select
import time
import multiprocessing
import inspect

from . import icon_gen
from . import utils

def build_all():
  utils.del_env_vars('CC', 'CXX')

  if utils.is_x64_host():
    subprocess.run(['cargo', 'build', '--release', '--target', 'x86_64-unknown-linux-gnu' ] + utils.get_addtl_cargo_args(), check=True)

  elif utils.is_aarch64_host():
    subprocess.run(['cargo', 'build', '--release', '--target', 'aarch64-unknown-linux-gnu' ] + utils.get_addtl_cargo_args(), check=True)

  else:
    raise Exception('Unknown host CPU type!')



if __name__ == '__main__':
  build_all()

