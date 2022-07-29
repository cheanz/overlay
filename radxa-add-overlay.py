#!/usr/bin/python3

# Copyright (c) 2022 The Radxa Dev Team
# Author: setq <setq@radxa.com>
# Version: 0.1.1

import argparse

import os

import subprocess

BASEDIR = os.path.abspath(os.path.dirname(__file__))
shell = lambda x: subprocess.check_call(x, shell=True)
output = lambda x: subprocess.check_output(x, shell=True).strip().decode()# why doesnt specify decode parameter like(UTF-8).


hw_intfc = {
    'devspi1': 'spi1=on',
    'devspi2': 'spi2=on',
    'spi1-waveshare35b-v2': 'uart4=off,spi1=on',
    'spi1-waveshare35c': 'uart4=off,spi1=on',
    'spi1-flash': 'uart4=off,spi1=on',
    'hifiberry-dacplus': 'i2c7=on',
    'spi1-mcp2515-can0': 'uart4=off,spi1=on'
}


def get_path(fname, basedir=BASEDIR, not_exist_mk=False):
    if not os.path.isabs(fname):
        fname = os.path.join(basedir, fname)
    if not_exist_mk:
        parent = os.path.dirname(fname)
        if not os.path.exists(parent):
            os.makedirs(parent)
    return os.path.abspath(fname)


def turn_fc(fc):
    if fc:
        kv = {'on': 'off', 'off': 'on'}
        key, val = fc.split('=')
        fc = '%s=%s' % (key, kv[val])
    return fc


def get_series():
    sub_in = lambda arr, s: sum([1 for x in arr if x in s]) #return an integer sum for x both in arr and s
    model = output('cat /proc/device-tree/model').lower()   #return a lower case string
# recognize rockpi series
    if sub_in(['3a', '3b', '3c'], model):
        series = '3'
    elif sub_in(['4a', '4b', '4c'], model):
        series = '4'
    elif sub_in(['5a', '5b', '5c'], model):
        series = '5'
    elif sub_in(['pi s'], model):
        series = 's'
    else:
        series = 'unknown'

    return series


def comfirm(text):
    print(text)
    ans = input('Continue? [y/N] ')
    if ans.strip().lower() != 'y':
        print('Aborted.')
        exit(1)


def apt_install(package):
    comfirm('Package %s is required. Install now?' % package, end='')
    shell('apt-get update')
    shell('apt-get install %s' % package)


def get_config(args):
    if args.series in ['3', 's']:
        config = '/boot/uEnv.txt'
    elif args.series == '4':
        config = '/boot/hw_intfc.conf'
        if not os.path.exists(config):
            apt_install('rockpi4-dtbo')
    elif args.series == '5':                    #rockpi5 config is stored in this path
        config = '/boot/extlinux/extlinux.conf'
    else:
        config = 'unknown'
    return config


def get_overlay(args):
    if args.series == '4':                                              # arg.series
        overlays = '/boot/overlays'
    else:
        overlays = '/boot/dtbs/%s/rockchip/overlay' % output('uname -r')

    if args.type == 'dts':
        args.dtbo = args.name                                           # args.dtbo  to be added
        src = get_path(args.input)
        dst = '/tmp/%s.dtbo' % args.name                                # new variable
        if 'not found' in output('type dtc | tee'):                     # if no dtc, install it.
            apt_install('device-tree-compiler')
        shell('dtc -q -I dts -O dtb -o %s %s' % (dst, src))             # ??????
        shell('cp %s %s' % (dst, overlays))
    else:
        args.dtbo = args.input

    if not os.path.exists(get_path(args.dtbo, basedir=overlays) + '.dtbo'):
        print('Overlay not found.')
        exit(1)


def apply_modify(args):
    dtbo, config = args.dtbo, args.config
    shell('cp %s %s' % (config, config + '.bak'))

    with open(config, 'r') as f:
        conf = f.read()

    if args.series == '4':
        for fc in hw_intfc.get(dtbo, '').split(','):
            conf = conf.replace(turn_fc(fc), fc)

        to_add = 'intfc:dtoverlay=%s' % dtbo
        if '#%s' % to_add in conf:
            conf = conf.replace('#%s' % to_add, to_add)
        else:
            conf = conf + '%s\n' % to_add
    elif args.series == '5':
        tmp = []
        dtbo = '/dtbs/%s/rockchip/overlay/%s.dtbo' % (output('uname -r'), dtbo)
        if 'fdtoverlays' in conf:
            for line in conf.strip().split('\n'):
                if 'fdtoverlays' in line:
                    line = line + ' ' + dtbo
                tmp.append(line)
        else:
            for line in conf.strip().split('\n'):
                if ('devicetreedir /dtbs/%s' % output('uname -r')) in line:
                    line = line + '\n    fdtoverlays %s' % dtbo
                tmp.append(line)
        conf = '\n'.join(tmp) + '\n'
    else:  # 3, s
        tmp = []
        for line in conf.strip().split('\n'):
            if 'overlays' in line and dtbo not in line:
                line = line + ' ' + dtbo
            tmp.append(line)
        conf = '\n'.join(tmp) + '\n'
        if 'overlays' not in conf:
            conf = conf + 'overlays=%s\n' % dtbo

    with open(config, 'w') as f:
        f.write(conf)

    print('Reboot is required to apply the changes.')


def main(args):
    args.series = get_series()
    args.config = get_config(args)

    if args.list:

        if args.series == '4':                                              # arg.series
            overlaysl = '/boot/overlays'
        else:
            overlaysl = '/boot/dtbs/%s/rockchip/overlay' % output('uname -r')

        # shell("find %s -name '*.dtbo' -printf '%P\n' " %(overlaysl))
        # 0.6 shell("find %s -name '*.dtbo' " %(overlaysl))

        #0.7
        # shell("cd %s" %(overlaysl))
        # shell("ls *.dtbo ")
        
        #0.8
        shell("find %s -name '*.dtbo' -exec basename {} \; " %(overlaysl))

    if not args.type and args.input:                                               #if the command didnt specify --type, decide its type
        if '.' in args.input:                                       #dts
            args.type = os.path.splitext(args.input)[1][1:]
        else:
            args.type = 'dtbo'                                      #exiting dtbo
    if not args.name and args.type != 'dtbo' and args.input:                       #
        args.name = os.path.splitext(args.input)[0].split('/')[-1]
    
    
    if args.input:
        get_overlay(args)
        apply_modify(args)
    


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    #required= True removed
    args.add_argument('-i', '--input', help='Input file') # -i must be specified unlike the other two arguments
    args.add_argument('-t', '--type', help='Input type')
    args.add_argument('-n', '--name', help='Name of the overlay')
    #
    args.add_argument('-l', '--list', help='List all the available dtbos under overlay',nargs='?',type = bool, const=True, default=False)
  
    args = args.parse_args()

    main(args)
