
import os
import sys
import subprocess
import time
import traceback

import btool

from . import utils

from . import build_common_pre_exe
from . import build_linux
from . import build_macos
from . import build_windows
from . import build_common_post_exe

def recompile_and_kill_and_reexec(old_test_proc, cmd_to_exec):
  try:
    if utils.is_linux_host():
      print('Compiling all Linux targets...')
      build_linux.build_all()

    if utils.is_macos_host():
      print('Compiling all MacOS targets...')
      build_macos.build_all()

    if utils.is_windows_host():
      print('Compiling all Windows targets...')
      build_windows.build_all()
  except:
    traceback.print_exc()
    return

  if old_test_proc is not None:
    utils.maybe(lambda: old_test_proc.kill() );

  return subprocess.Popen(cmd_to_exec)

dict_of_mtime_file_hashes = {}

def block_until_newer_mtime_in_dir_or_proc_dies(test_proc, directory, mtime_to_beat, poll_ms=250):
  global dict_of_mtime_file_hashes
  best_mtime = 0
  while best_mtime <= mtime_to_beat:
    time.sleep(poll_ms / 1000.0)

    if test_proc is not None:
      if test_proc.poll() is not None:
        # subprocess is dead
        break

    for root, dirs, files in os.walk(directory):
      for f in files:
        f = os.path.join(root, f)
        
        # Skip if f's content hash() is the same as the one in dict_of_mtime_file_hashes[f]
        current_file_hash = ''
        with open(f, 'r') as fd:
          current_file_hash = hash(fd.read())

        if f in dict_of_mtime_file_hashes:
          if dict_of_mtime_file_hashes[f] == current_file_hash:
            continue
        
        # File hash is new/different, compare mtime
        dict_of_mtime_file_hashes[f] = current_file_hash

        f_mtime = os.path.getmtime(f)
        if f_mtime > best_mtime:
          best_mtime = f_mtime

  return best_mtime


def main(args=sys.argv):

  utils.cd_up_to_repo_root()

  build_common_pre_exe.build_all()

  # Additional arguments will be executed, waited on, and killed/re-executed when src changes.
  # build_common_pre_exe WILL NOT be re-run between source changes, only Meili itself will be re-built.
  test_cmd = sys.argv[1:]

  src_dir = os.path.abspath(os.path.join('src'))

  mtime_to_beat = 0
  old_test_proc = None

  try:
    while True:
      mtime_to_beat = block_until_newer_mtime_in_dir_or_proc_dies(old_test_proc, src_dir, mtime_to_beat)
      print('> {}'.format(' '.join(test_cmd)))
      old_test_proc = recompile_and_kill_and_reexec(old_test_proc, test_cmd)
      
  except KeyboardInterrupt as e:
    pass
  except:
    traceback.print_exc()

  if old_test_proc is not None:
    utils.maybe(lambda: old_test_proc.terminate())

  


if __name__ == '__main__':
  main()
