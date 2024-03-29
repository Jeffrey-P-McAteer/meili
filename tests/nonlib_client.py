
import os
import sys
import subprocess
import socket
import importlib

# Utility method to wrap imports with a call to pip to install first.
# > "100% idiot-proof!" -- guy on street selling rusty dependency chains.
def import_maybe_installing_with_pip(import_name, pkg_name=None):
  if pkg_name is None:
    pkg_name = import_name # 90% of all python packages share their name with their module
  pkg_spec = importlib.util.find_spec(import_name)
  install_cmd = []
  if pkg_spec is None:
    # package missing, install via pip to user prefix!
    print('Attempting to install module {} (package {}) with pip...'.format(import_name, pkg_name))
    install_cmd = [sys.executable, '-m', 'pip', 'install', '--user', pkg_name]
    subprocess.run(install_cmd, check=False)
  pkg_spec = importlib.util.find_spec(import_name)
  if pkg_spec is None:
    raise Exception('Cannot find module {}, attempted to install {} via pip: {}'.format(import_name, pkg_name, ' '.join(install_cmd) ))
  
  return importlib.import_module(import_name)

# 3rd-party pip packages
bare = import_maybe_installing_with_pip('bare', pkg_name='pybare')

from bare import Struct, Map, Str, UInt, U64, Optional, DataFixed

class ServerTestStruct(Struct):
  flags = U64()
  sn = Str()
  db = Str()
  sql = Str()
  


def main(args=sys.argv):
  tcp_bare_server = ('127.0.0.1', 4430)
  print('Sending a BARE message to {}'.format(tcp_bare_server))

  s = ServerTestStruct(flags=1, sn="localhost", db="db01", sql="select * from table02 where rowid < 10 limit 10;")
  
  message = s.pack()

  s_roundabout = ServerTestStruct().unpack(message)

  print('s={}'.format(s))
  print('message={}'.format(message))
  print('message={}'.format([int(x) for x in message]))
  print('message={}'.format([hex(x) for x in message]))
  
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.connect(tcp_bare_server)
  sock.send(message)
  #sock.sendall(message)
  #sock.sendall(message + (7 * b'\000') )

  # Wait for a reply
  data = sock.recv(1024)
  print('data={}'.format(data))




if __name__ == '__main__':
  main()


