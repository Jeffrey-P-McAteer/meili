
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

import plistlib # apparently python just ships with this on all platforms?

from . import icon_gen
from . import utils

def build_all():
  # Now that we have all target .exes built, package them
  if utils.can_compile_macos():
    build_macos_app_bundle()
  
  print_macos_exe_locations()

  print_windows_exe_locations()

  print_linux_exe_locations()


def print_linux_exe_locations():
  linux_client_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-unknown-linux-gnu', 'release', 'meili-client'),
    os.path.join('target', 'aarch64-unknown-linux-gnu', 'release', 'meili-client'),
  )
  linux_server_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-unknown-linux-gnu', 'release', 'meili-server'),
    os.path.join('target', 'aarch64-unknown-linux-gnu', 'release', 'meili-server'),
  )

  if linux_client_exe:
    print('Linux client is located at {}'.format(os.path.abspath(linux_client_exe)))

  if linux_server_exe:
    print('Linux server is located at {}'.format(os.path.abspath(linux_server_exe)))


def print_windows_exe_locations():
  windows_client_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-pc-windows-gnu', 'release', 'meili-client.exe'),
    os.path.join('target', 'x86_64-pc-windows-msvc', 'release', 'meili-client.exe'),
    os.path.join('target', 'aarch64-pc-windows-msvc', 'release', 'meili-client.exe'),
  )
  windows_server_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-pc-windows-gnu', 'release', 'meili-server.exe'),
    os.path.join('target', 'x86_64-pc-windows-msvc', 'release', 'meili-server.exe'),
    os.path.join('target', 'aarch64-pc-windows-msvc', 'release', 'meili-server.exe'),
  )

  if windows_client_exe:
    print('Windows client.exe is located at {}'.format(os.path.abspath(windows_client_exe)))

  if windows_server_exe:
    print('Windows server.exe is located at {}'.format(os.path.abspath(windows_server_exe)))

def print_macos_exe_locations():
  macos_client_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-apple-darwin', 'release', 'meili-client'),
    os.path.join('target', 'aarch64-apple-darwin', 'release', 'meili-client'),
  )
  macos_server_exe = utils.get_first_existing(
    os.path.join('target', 'x86_64-apple-darwin', 'release', 'meili-server'),
    os.path.join('target', 'aarch64-apple-darwin', 'release', 'meili-server'),
  )

  if macos_client_exe:
    print('MacOS client is located at {}'.format(os.path.abspath(macos_client_exe)))

  if macos_server_exe:
    print('MacOS server is located at {}'.format(os.path.abspath(macos_server_exe)))
    

def build_macos_app_bundle():
  client_exe = utils.get_most_recent_mtimed(
    os.path.abspath( os.path.join( 'target', 'x86_64-apple-darwin', 'release', 'meili-client' ) ),
    os.path.abspath( os.path.join( 'target', 'aarch64-apple-darwin', 'release', 'meili-client' ) ),
  )

  # use client_exe to create target/Meili.app, a directory
  # conforming to apple's app setup.
  Meili_app = os.path.abspath( os.path.join('target', 'Meili.app') )
  os.makedirs(Meili_app, exist_ok=True)
  os.makedirs(os.path.join(Meili_app, 'Contents', 'Resources'), exist_ok=True)
  
  files_to_copy = [
    (client_exe, os.path.join(Meili_app, 'Meili')),
    (os.path.join('target', 'Meili.icns'), os.path.join(Meili_app, 'Contents', 'Resources', 'AppIcon.icns')),
  ]
  for src_f, dst_f in files_to_copy:
    try:
      shutil.copy(src_f, dst_f)
    except shutil.SameFileError:
      pass # why bother? Ugh.

  # Finally create Contents/Info.plist
  #plistlib = utils.import_maybe_installing_with_pip('plistlib') # python SHIPS with this! Woah.

  plist_data = dict(
    CFBundleDisplayName='Meili',
    CFBundleName='Meili',
    CFBundleExecutable=os.path.join('Meili'),
    CFBundleIconFile=os.path.join('Contents', 'Resources', 'AppIcon.icns'), # Legacy apparently?
    #CFBundleIconName='', # TODO research asset catalog & use this; potential light + dark-mode icons?
    CFBundleIdentifier='pw.jmcateer.meili-client',
    NSHighResolutionCapable=True,
  )

  with open(os.path.join(Meili_app, 'Contents', 'Info.plist'), 'wb') as fd:
    plistlib.dump(plist_data, fd)


  print('MacOS Meili Client .app created at {}'.format(Meili_app))


  # Now put .app in .dmg w/ background image!
  if shutil.which('mkfs.hfsplus'):
    dmg_image_size_bytes = utils.directory_size_bytes(Meili_app)
    dmg_image_size_bytes *= 1.35 # assume hfs+ needs 35% overhead for bookkeeping

    dmg_image_size_mbytes = int(dmg_image_size_bytes / 1000000)

    dmg_file = os.path.abspath(os.path.join('target', 'Meili.dmg'))
    dmg_mountpoint = os.path.abspath(os.path.join('target', 'Meili.dmg_mount'))

    if os.path.exists(dmg_mountpoint):
      subprocess.run(['sudo', 'umount', dmg_mountpoint], check=False) # not fatal if process dies, we just need to try before removing .dmg file
    os.makedirs(dmg_mountpoint, exist_ok=True)

    if os.path.exists(dmg_file):
      os.remove(dmg_file)

    utils.run_silent_cmd('dd', 'if=/dev/zero', 'of={}'.format(dmg_file), 'bs=1M', 'count={}'.format(dmg_image_size_mbytes))
    utils.run_silent_cmd('mkfs.hfsplus', '-v', 'InstallMeili', '-M', '777', dmg_file)

    utils.run_silent_cmd('sudo', 'mount', '-o', 'loop', dmg_file, dmg_mountpoint)

    # Begin adding to .dmg
    shutil.copytree(Meili_app, os.path.join(dmg_mountpoint, os.path.basename(Meili_app)))

    #spotlight_vol_plist = os.path.join(dmg_mountpoint, '.Spotlight-V100', 'VolumeConfiguration.plist')
    #os.makedirs(os.path.dirname(spotlight_vol_plist), exist_ok=True)
    #plist_data = dict(
    #  
    #)
    #with open(os.path.join(spotlight_vol_plist), 'wb') as fd:
    #  plistlib.dump(plist_data, fd)

    # End adding to .dmg

    subprocess.run(['sudo', 'umount', dmg_mountpoint], check=False)
    os.rmdir(dmg_mountpoint)

    print('MacOS Meili Client .dmg created at {}'.format(dmg_file))


  elif shutil.which('hdiutil'):
    dmg_file = os.path.abspath(os.path.join('target', 'Meili.dmg'))
    dmg_mountpoint = os.path.abspath(os.path.join('target', 'Meili.dmg_mount'))
    if os.path.exists(dmg_mountpoint):
      shutil.rmtree(dmg_mountpoint)
    os.makedirs(dmg_mountpoint, exist_ok=True)

    # Begin adding to .dmg
    shutil.copytree(Meili_app, os.path.join(dmg_mountpoint, os.path.basename(Meili_app)))
    # .dmg contains ./Meili.app, anything else?

    # End adding to .dmg

    utils.run_silent_cmd(
      'hdiutil', 'create', '-volname', 'InstallMeili', '-srcfolder', dmg_mountpoint, '-ov', '-format', 'UDZO', dmg_file
    )

    print('MacOS Meili Client .dmg created at {}'.format(dmg_file))









