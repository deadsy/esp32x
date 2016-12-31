# ----------------------------------------------------------------------------
"""
Input/Output Buffer Objects
Stateful objects used to produce/consume data from JTAG devices
"""
# ----------------------------------------------------------------------------

import sys
import string
import struct
import hashlib
import time

import util

# ----------------------------------------------------------------------------

printable = string.letters + string.digits + string.punctuation + ' '

#-----------------------------------------------------------------------------

class write_file(object):

  def __init__(self, ui, msg, name, size, mode = 'le'):
    self.ui = ui
    self.f = open(name, 'wb')
    self.n = 0
    self.fmt16 = ('>H', '<H')[mode == 'le']
    self.fmt32 = ('>L', '<L')[mode == 'le']
    # display output
    self.ui.put('%s ' % msg)
    self.progress = util.progress(ui, 8, size)

  def close(self):
    self.f.close()
    self.progress.erase()
    self.ui.put('done\n')

  def wr32(self, val):
    self.f.write(struct.pack(self.fmt32, val))
    self.n += 4
    self.progress.update(self.n)

  def wr16(self, val):
    self.f.write(struct.pack(self.fmt16, val))
    self.n += 2
    self.progress.update(self.n)

  def wr8(self, val):
    self.f.write(struct.pack('B', val))
    self.n += 1
    self.progress.update(self.n)

#-----------------------------------------------------------------------------

class read_file(object):

  def __init__(self, ui, msg, name, size, mode = 'le'):
    self.ui = ui
    self.f = open(name, 'rb')
    self.n = 0
    self.fmt16 = ('>H', '<H')[mode == 'le']
    self.fmt32 = ('>L', '<L')[mode == 'le']
    # display output
    self.t_start = time.time()
    self.ui.put('%s ' % msg)
    self.progress = util.progress(ui, 8, size)

  def close(self, rate = False):
    t_end = time.time()
    self.f.close()
    self.progress.erase()
    if rate:
      s = '%.2f KiB/sec' % (float(self.n)/((t_end - self.t_start) * 1024.0))
      self.ui.put('done (%s)\n' % s)
    else:
      self.ui.put('done\n')

  def rd32(self):
    val = self.f.read(4)
    n = len(val)
    if n != 4:
      val = ''.join([val, '\xff' * (4 - n)])
    self.n += 4
    self.progress.update(self.n)
    return struct.unpack(self.fmt32, val)[0]

  def rd16(self):
    val = self.f.read(2)
    n = len(val)
    if n != 2:
      val = ''.join([val, '\xff' * (2 - n)])
    self.n += 2
    self.progress.update(self.n)
    return struct.unpack(self.fmt16, val)[0]

  def rd8(self):
    val = self.f.read(1)
    n = len(val)
    if n == 0:
      val = '\xff'
    self.n += 1
    self.progress.update(self.n)
    return struct.unpack('B', val)[0]

#-----------------------------------------------------------------------------

class verify_file(object):

  def __init__(self, ui, msg, name, size, mode = 'le'):
    self.ui = ui
    self.f = open(name, 'rb')
    self.n = 0
    self.diff = []
    self.fmt16 = ('>H', '<H')[mode == 'le']
    self.fmt32 = ('>L', '<L')[mode == 'le']
    # display output
    self.ui.put('%s ' % msg)
    self.progress = util.progress(ui, 8, size)

  def close(self):
    self.f.close()
    self.progress.erase()
    if len(self.diff) == 0:
      self.ui.put('same\n')
    else:
      self.ui.put('%d differences\n' % len(self.diff))

  def file_rd32(self):
    val = self.f.read(4)
    n = len(val)
    if n != 4:
      val = ''.join([val, '\xff' * (4 - n)])
    return struct.unpack(self.fmt32, val)[0]

  def wr32(self, val):
    x = self.file_rd32()
    if val != x:
      self.diff.append((self.n, val, x))
    self.n += 4
    self.progress.update(self.n)

#-----------------------------------------------------------------------------

class data_buffer(object):

  def __init__(self, width, data = None):
    self.width = width
    self.buf = []
    if data:
      mask = util.mask(self.width)
      self.buf = [x & mask for x in data]
    self.wr_idx = len(self.buf)
    self.rd_idx = 0

  def copy(self):
    """return a copy of this buffer"""
    return data_buffer(self.width, self.buf)

  def read(self):
    """read from the data buffer"""
    val = self.buf[self.rd_idx]
    self.rd_idx += 1
    return val

  def write(self, val):
    """write to the data buffer"""
    val = util.mask_val(val, self.width)
    if self.wr_idx == len(self.buf):
      # append to the buffer
      self.buf.append(val)
      self.wr_idx += 1
    elif self.wr_idx < len(self.buf):
      # replace existing content
      self.buf[self.wr_idx] = val
    else:
      assert False, 'buffer write error: more than 1 off the end'

  def rd32(self):
    assert self.width == 32
    return self.read()

  def rd16(self):
    assert self.width == 16
    return self.read()

  def rd8(self):
    assert self.width == 8
    return self.read()

  def wr32(self, val):
    assert self.width == 32
    self.write(val)

  def wr16(self, val):
    assert self.width == 16
    self.write(val)

  def wr8(self, val):
    assert self.width == 8
    self.write(val)

  def convert8(self, mode):
    """convert the buffer to 8 bit values"""
    if self.width == 32:
      new_buf = []
      for x in self.buf:
        if mode == 'be':
          # big endian conversion
          new_buf.append((x >> 24) & 255)
          new_buf.append((x >> 16) & 255)
          new_buf.append((x >> 8) & 255)
          new_buf.append(x & 255)
        else:
          # little endian conversion
          new_buf.append(x & 255)
          new_buf.append((x >> 8) & 255)
          new_buf.append((x >> 16) & 255)
          new_buf.append((x >> 24) & 255)
      self.buf = new_buf
    elif self.width == 16:
      new_buf = []
      for x in self.buf:
        if mode == 'be':
          # big endian conversion
          new_buf.append((x >> 8) & 255)
          new_buf.append(x & 255)
        else:
          # little endian conversion
          new_buf.append(x & 255)
          new_buf.append((x >> 8) & 255)
      self.buf = new_buf
    elif self.width == 8:
      # nothing to do
      return
    else:
      assert False, 'conversion error: width %d' % self.width
    # reset the buffer indices
    self.wr_idx = len(self.buf)
    self.rd_idx = 0
    self.width = 8

  def convert16(self, mode):
    """convert the buffer to 16 bit values"""
    if self.width == 32:
      new_buf = []
      for x in self.buf:
        if mode == 'be':
          # big endian conversion
          new_buf.append((x >> 16) & 0xffff)
          new_buf.append(x & 0xffff)
        else:
          # little endian conversion
          new_buf.append(x & 0xffff)
          new_buf.append((x >> 16) & 0xffff)
      self.buf = new_buf
    elif self.width == 16:
      # nothing to do
      return
    elif self.width == 8:
      # round up to a multiple of 2 bytes
      n = len(self.buf) & 1
      self.buf.extend((0,) * n)
      new_buf = []
      for i in range(0, len(self.buf), 2):
        if mode == 'be':
          # big endian conversion
          val = (self.buf[i] << 8) | self.buf[i+1]
        else:
          # little endian conversion
          val = self.buf[i] | (self.buf[i+1] << 8)
        new_buf.append(val)
      self.buf = new_buf
    else:
      assert False, 'conversion error: width %d' % self.width
    # reset the buffer indices
    self.wr_idx = len(self.buf)
    self.rd_idx = 0
    self.width = 16

  def convert32(self, mode):
    """convert the buffer to 32 bit values"""
    if self.width == 32:
      # nothing to do
      return
    elif self.width == 16:
      assert False, 'TODO: unsupported conversion from 16 to 32 bits'
    elif self.width == 8:
      # round up to a multiple of 4 bytes
      n = (4 - (len(self.buf) & 3)) & 3
      self.buf.extend((0,) * n)
      new_buf = []
      for i in range(0, len(self.buf), 4):
        if mode == 'be':
          # big endian conversion
          val = ((self.buf[i] << 24) |
                 (self.buf[i+1] << 16) |
                 (self.buf[i+2] << 8) |
                 (self.buf[i+3]))
        else:
          # little endian conversion
          val = (self.buf[i] |
                 (self.buf[i+1] << 8) |
                 (self.buf[i+2] << 16) |
                 (self.buf[i+3] << 24))
        new_buf.append(val)
      self.buf = new_buf
    else:
      assert False, 'conversion error: width %d' % self.width
    # reset the buffer indices
    self.wr_idx = len(self.buf)
    self.rd_idx = 0
    self.width = 32

  def convert(self, width, mode):
    if width == 8:
      self.convert8(mode)
    elif width == 16:
      self.convert16(mode)
    elif width == 32:
      self.convert32(mode)
    else:
      assert False, 'bad width'

  def endian_swap(self):
    """swap the endian-ness of all values"""
    if self.width == 32:
      self.buf = [util.swap32(x) for x in self.buf]
    elif self.width == 16:
      self.buf = [util.swap16(x) for x in self.buf]
    elif self.width == 8:
      # nothing to do
      return
    else:
      assert False, 'endian swap error: width %d' % self.width

  def compare(self, x):
    """compare io buffers: return True if they are the same"""
    if self.width != x.width:
      return False
    if len(self.buf) != len(x.buf):
      return False
    for i in xrange(len(self.buf)):
      if self.buf[i] != x.buf[i]:
        return False
    return True

  def md5(self, mode):
    """return an md5 hash of the buffer"""
    x = self.copy()
    x.convert8(mode)
    m = hashlib.md5()
    m.update(''.join([chr(b) for b in x.buf]))
    return m.hexdigest()

  def ascii_str(self):
    """return an ascii string representing an 8-bit buffer"""
    assert self.width == 8, 'width must be 8 bits'
    return ''.join([('.', chr(b))[chr(b) in printable] for b in self.buf])

  def to_str(self):
    """convert an 8-bit buffer to a string"""
    assert self.width == 8, 'width must be 8 bits'
    return ''.join([chr(b) for b in self.buf])

  def __len__(self):
    return len(self.buf)

  def __str__(self):
    """return a string for the buffer values"""
    fmt = '%%0%dx' % (self.width / 4)
    return ' '.join([fmt % x for x in self.buf])

#-----------------------------------------------------------------------------
