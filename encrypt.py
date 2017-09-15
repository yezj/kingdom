# coding=utf-8
import os
import sys
import string
from random import *


def random_characters(min, max):
    characters = string.ascii_letters + string.punctuation + string.digits + 'ا ب ة ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه'
    return "".join(choice(characters) for x in range(randint(min, max)))


def walk_dirs(path):
    dir_path, dir_name = os.path.split(path)
    new_dir_name = dir_name + '_bak'
    new_dir_path = '{}/{}'.format(dir_path, new_dir_name)
    os.system('cp -r %s %s' % (path, new_dir_path))
    for root, dirs, files in os.walk(new_dir_path, topdown=False):
        for name in files:
            if name.endswith('.jpg') or name.endswith('.png'):
                current_file_name = os.path.join(root, name)
                print(os.path.join(root, name))
                new_file_name = current_file_name.replace('png', 'px')
                os.rename(current_file_name, new_file_name)
                operate(new_file_name)
        for name in dirs:
            if name.endswith('.jpg') or name.endswith('.png'):
                current_file_name = os.path.join(root, name)
                print(os.path.join(root, name))
                new_file_name = current_file_name.replace('png', 'px')
                os.rename(current_file_name, new_file_name)
                operate(new_file_name)


def operate(file_name):
    try:
        f = open(file_name, 'r+')
        s = f.read()
        # print len(s)
        s.index('IDAT')
        f.seek(0)
        character_16 = random_characters(16, 16)
        # print 'character_16', character_16
        f.write(character_16)
        f.seek(16)
        f.write(random_characters(2, 2))
        f.seek(20)
        f.write(random_characters(2, 2))
        #
        pos = s.index('IDAT')
        f.seek(pos)
        f.write(random_characters(4, 4))

        f.seek(12)
        f.write(hex(pos).replace('0x', '').zfill(4))

        f.seek(len(s) - 12)
        end_characters = random_characters(64, 99)
        f.write(end_characters)
        # print len(end_characters), end_characters

        f.seek(0)
        s = f.read()
        # print len(s)
        f.seek(len(s) - 57)
        f.write(hex(len(end_characters)).replace('0x', ''))
        f.close()
    except Exception as e:
        print e.message


if __name__ == "__main__":
    if len(sys.argv) > 1:
        walk_dirs(sys.argv[1])
    else:
        print 'python encrypt.py filepath'
