# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
############################################################################
#
# MODULE: r3.slice
# AUTHOR(S): Anna Petrasova
# PURPOSE: Computes vertical slice based on two points
#
# COPYRIGHT: (C) 2019 by Glynn Clements
#
#   This program is free software under the GNU General Public
#   License (>=v2). Read the file COPYING that comes with GRASS
#   for details.
#
#############################################################################

#%Module
#% description: Creates a vertical slice of a 3D raster in arbitrary direction and places it in 0,0 coordinates.
#% keywords: 3D raster
#%end
#%option G_OPT_R3_INPUT
#%end
#%option G_OPT_R_OUTPUT
#%end
#%option G_OPT_V_OUTPUT
#% key: axes
#% description: Draw vector map representing axes
#% required: no
#%end
#%option G_OPT_V_OUTPUT
#% key: slice_line
#% description: Draw vector line representing slice
#% required: no
#%end
#%option G_OPT_M_COORDS
#% multiple: yes
#% key_desc: x,y,x,y
#%end
#%option
#% key: units
#% multiple: yes
#% required: no
#% description: units for horizontal and vertical axes
#% key_desc: unit1,unit2
#%end
#%option
#% key: offset
#% multiple: yes
#% required: no
#% description: offset slice placement in percents
#% key_desc: x,y
#%end

import os
import atexit

from grass.script import core as gcore

PREFIX = 'r3_to_rast_tmp_' + str(os.getpid())


def cleanup():
    gcore.run_command('g.remove', flags='f', pattern=PREFIX + '*', type='raster')


def main(input_, coordinates, output, axes, slice_line, units, offset):
    prefix = 'r3_to_rast_tmp_' + str(os.getpid())
    gcore.run_command('r3.to.rast', input=input_, output=prefix)
    maps = gcore.read_command('g.list', type='raster', pattern=PREFIX + '*').strip().split(os.linesep)
    region = gcore.region(region3d=True)
    res = (region['ewres'] + region['nsres']) / 2.
    if coordinates[0][0] > coordinates[1][0]:
        coordinates = (coordinates[1], coordinates[0])
    profile = gcore.read_command('r.profile', coordinates=coordinates,
                                 input=maps[0], output='-').strip().split(os.linesep)
    cols = len(profile)
    rows = len(maps)
    s = w = 0
    e = cols * res
    n = rows * region['tbres']
    if offset:
        offset[0] = w + (e - w) * float(offset[0])
        offset[1] = (n - s) * float(offset[1])
        e += offset[0]
        w += offset[0]
        n += offset[1]
        s += offset[1]
    ascii_input = [("north: {n}\nsouth: {s}\neast: {e}\nwest: {w}\n"
                   "rows: {r}\ncols: {c}\n".format(n=n, s=s, e=e, w=w, r=rows, c=cols))]
    for map_ in reversed(maps):
        profile = gcore.read_command('r.profile', coordinates=coordinates,
                                     input=map_, output='-', quiet=True).strip().split(os.linesep)
        ascii_input.append(' '.join([line.split()[1] for line in profile]))

    gcore.write_command('r.in.ascii', input='-', stdin='\n'.join(ascii_input),
                        output=output, type='FCELL')

    gcore.run_command('r.colors', map=output, raster_3d=input_)

    if slice_line:
        vector_ascii = []
        vector_ascii.append('L 2 1')
        vector_ascii.append('{x} {y}'.format(x=coordinates[0][0], y=coordinates[0][1]))
        vector_ascii.append('{x} {y}'.format(x=coordinates[1][0], y=coordinates[1][1]))
        vector_ascii.append('1 1')
        gcore.write_command('v.in.ascii', format='standard', input='-', stdin='\n'.join(vector_ascii),
                            flags='n', output=slice_line)

    if axes:
        vector_ascii = []
        vector_ascii.append('L 2 1')
        vector_ascii.append('{x} {y}'.format(x=w, y=n + 0.1 * (n - s)))
        vector_ascii.append('{x} {y}'.format(x=e, y=n + 0.1 * (n - s)))
        vector_ascii.append('1 1')
        vector_ascii.append('P 1 1')
        vector_ascii.append('{x} {y}'.format(x=w, y=n + 0.1 * (n - s)))
        vector_ascii.append('2 1')
        vector_ascii.append('P 1 1')
        vector_ascii.append('{x} {y}'.format(x=e, y=n + 0.1 * (n - s)))
        vector_ascii.append('2 2')

        vector_ascii.append('L 2 1')
        vector_ascii.append('{x} {y}'.format(x=e + 0.05 * (e - w), y=n))
        vector_ascii.append('{x} {y}'.format(x=e + 0.05 * (e - w), y=s))
        vector_ascii.append('2 3')
        vector_ascii.append('P 1 1')
        vector_ascii.append('{x} {y}'.format(x=e + 0.05 * (e - w), y=n))
        vector_ascii.append('1 2')
        vector_ascii.append('P 1 1')
        vector_ascii.append('{x} {y}'.format(x=e + 0.05 * (e - w), y=s))
        vector_ascii.append('1 3')

        gcore.write_command('v.in.ascii', format='standard', input='-', stdin='\n'.join(vector_ascii),
                            flags='n', output=axes)
        if units:
            units = units.split(',')
        else:
            units = ['', '']
        gcore.run_command('v.db.addtable', map=axes, layer=1, columns="label varchar(50)")
        sql = ('UPDATE {axes} SET label = "{length} {u1}" WHERE cat = 1;\n'
               'UPDATE {axes} SET label = "{top} {u2}" WHERE cat = 2;\n'
               'UPDATE {axes} SET label = "{bottom} {u2}" WHERE cat = 3;\n'.format(axes=axes, length=int(e - w),
                                                                            top=region['t'], bottom=region['b'],
                                                                            u1=units[0], u2=units[1]))
        gcore.write_command('db.execute', input='-', stdin=sql)

if __name__ == '__main__':
    options, flags = gcore.parser()
    atexit.register(cleanup)

    coordinates = options['coordinates'].strip(',').split(',')
    if len(coordinates) != 4:
        gcore.fatal(_("Please provide 2 coordinates."))
    coordinates = zip(map(float, coordinates[0::2]), map(float, coordinates[1::2]))
    if options['offset']:
        offset = [float(each) / 100 for each in options['offset'].split(',')]
    else:
        offset = None
    main(options['input'], coordinates, options['output'],
         axes=options['axes'], slice_line=options['slice_line'], units=options['units'], offset=offset)
