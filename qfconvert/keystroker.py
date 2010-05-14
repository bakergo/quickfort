from geometry import *
import util
import re

"""
KEY_LIST = {
        '[n]':config['KeyUp'],
        '[ne]':config['KeyUpRight'],
        '[e]':config['KeyRight'],
        '[se]':config['KeyDownRight'],
        '[s]':config['KeyDown'],
        '[sw]':config['KeyDownLeft'],
        '[w]':config['KeyLeft'],
        '[nw]':config['KeyUpLeft'],
        '[u]':config['KeyUpZ'],
        '[d]':config['KeyDownZ'],
        '!':config['KeyCommit'],
        '^':config['KeyExitMenu']
    }
"""

KEY_LIST = {
    '[n]': '8', '[ne]': '9', '[e]': '6', '[se]': '3', '[s]': '2', '[sw]': '1', '[w]': '4', '[nw]': '7',
    '[widen]': 'k',
    '[heighten]': 'u',
    '[menudown]': '{NumpadAdd}',
    '!': '{Enter}',
    '#': '+{Enter}',
    '%': '%wait%',
    '^': '{Esc}'
}



class Keystroker:

    def __init__(self, grid, buildconfig):
        self.grid = grid
        self.buildconfig = buildconfig
        self.current_menu = None

    def plot(self, plots, cursor):
        submenukeys = self.buildconfig.get('submenukeys')
        last_command = ''
        last_submenu = ''
        keys = self.buildconfig.get('init') or []
        # print 'starting plot in keystroker'
        # print [str(p) for p in plots]
        # print keys
        # construct the list of keystrokes required to move to each
        # successive area and build it
        for pos in plots:
            cell = self.grid.get_cell(pos)
            command = cell.command
            endpos = cell.area.opposite_corner(pos)
            subs = {}

            # only want to send (nonmenu) key command when we
            # need to switch modes for dig, but for build
            # we have to press the command key every time
            # new config vars 'samecmd', 'diffcmd'
            #  for 'd': [], ['cmd']
            #  for 'b': ['cmd'], ['cmd']
            # so when processing the 'cmd' replacement, get
            # one of these from cfg, and replace into that
            # .. plus submenu in/out logic, where if we change
            #    submenus (indeed if the last_command does not
            #    exactly match command), reset last_command to ''

            # get samecmd or diffcmd depending
            if command == last_command:
                nextcmd = self.buildconfig.get('samecmd', command) or []
            else:
                nextcmd = self.buildconfig.get('diffcmd', command) or []
                last_command = command

            # moveto = keys to move cursor to starting area-corner
            # TODO self.move should return special movement symbols
            # to be looked up in KEY_LIST; use a format in KEY_LIST
            # of [n], [s], [menudown], etc. to distinguish key-aliases
            # from {AHKKeys} and bare keystrokes
            subs['moveto'] = self.move(cursor, pos)

            # setsize = keys to set area to desired dimensions
            setsizefun = self.buildconfig.get('setsize', command)
            setsize, newpos = setsizefun(self, pos, endpos)
            subs['setsize'] = setsize

            # setmats - keys to select mats for an area
            setmatsfun = self.buildconfig.get('setmats', command)
            if setmatsfun:
                subs['setmats'] = self.setmats(cell.area.size())

            # submenu?
            justcommand = None
            for k in submenukeys:
                if re.match(k, command):
                    submenu = command[0]
                    # print '(*****' + submenu + ' - ' + last_submenu

                    # entering a submenu from not being in one?
                    if not last_submenu:
                        # print 'ENTER NEW MENU FROM NOT BEING IN ONE ' + submenu
                        subs['menu'] = submenu
                        subs['exitmenu'] = []
                        last_submenu = submenu
                    elif last_submenu != submenu:
                        # print 'DIFFERS, using ' + submenu
                        # exit previous submenu
                        subs['exitmenu'] = KEY_LIST['^']
                        # enter new menu
                        subs['menu'] = submenu
                        last_submenu = submenu
                    else:
                        # print 'SAME SUBMENU DO NADA ' + submenu
                        subs['menu'] = []
                        subs['exitmenu'] = []

                    # drop the submenu key from command
                    justcommand = command[1:]
                    continue
            if not justcommand:
                # print 'NO SUBMENU WITH COMMAND: ' + command
                if last_submenu:
                    # print 'EXITING THE LAST MENU WHICH WAS %s' % last_submenu
                    subs['exitmenu'] = KEY_LIST['^']
                else:
                    # print 'NO SUBMENU OR LAST SUBMENU, DOING NADA'
                    subs['exitmenu'] = []
                subs['menu'] = []
                last_submenu = ''
                justcommand = command[:]

            # break command into keys
            cmdedit = re.sub(r'\{', '|{', justcommand)
            cmdedit = re.sub(r'\}', '}|', cmdedit)
            cmdedit = re.sub(r'\!', '|!|', cmdedit)
            cmdkeys = re.split(r'\|', cmdedit)

            # substitute cmdkeys into nextcmd
            nextcmdkeys = []
            for c in nextcmd:
                if c == 'cmd':
                    nextcmdkeys.extend(cmdkeys)
                else:
                    nextcmd.append(c)

            # nextcmdkeys is now our command-key string
            subs['cmd'] = nextcmdkeys

            pattern = self.buildconfig.get('designate', command)

            newkeys = []
            # do pattern subs (and throw away empty elements)
            for p in pattern:
                if p in subs:
                    newkeys.extend(subs[p])
                else:
                    newkeys.append(p)

            # add our transformed keys to keys
            keys.extend(newkeys)

            # move cursor pos to end corner of built area
            cursor = newpos
        # print 'out of keystroker:'
        # print keys
        # print self.translate(keys)
        return keys

    def translate(self, keys):
        return util.flatten([self.translate_key(k) for k in keys])

    def translate_key(self, key):
        return KEY_LIST.get(key) or key

    def move(self, start, end):
        keys = []
        allow_backtrack = True

        # while there are moves left to make..
        while (start != end):
            direction = Direction.get_direction(start, end)

            # Get x and y component of distance between start and end
            dx = abs(start.x - end.x)
            dy = abs(start.y - end.y)

            if dx == 0:
                steps = dy # moving on y axis only
            elif dy == 0:
                steps = dx # moving on x axis only
            else:
                # determine max diagonal steps we can take
                # in this direction without going too far
                steps = min([dx, dy])

            keycode = ['[' + direction.compass + ']']
            move = direction.delta()
            if steps < 8 or not allow_backtrack:
                # render keystrokes
                keys.extend(keycode * steps)
                start = start + (move * steps)
                allow_backtrack = True
            else:
                jumps = (steps // 10)
                leftover = steps % 10
                jumpmove = move * 10

                # backtracking optimization
                if leftover >= 8:
                    # test if jumping an extra 10-unit step
                    # would put us outside of the bounds of
                    # the blueprint (want to prevent)
                    test = start + (jumpmove * (jumps + 1))

                    if self.grid.is_out_of_bounds(test):
                        # just move there normally
                        keys.extend(keycode * leftover)
                        start = start + (move * steps)
                        # don't try to do this next iteration
                        allow_backtrack = False
                    else:
                        # permit overjump/backtracking movement
                        jumps +=1
                        start = start + (jumpmove * jumps)
                        allow_backtrack = True
                else:
                    # move the last few cells needed when using
                    # jumpmoves to land on the right spot
                    keys.extend(keycode * leftover)
                    start = start + (move * steps)
                    allow_backtrack = True

                # shift optimization
                # this needs to be configured somewhere based
                # on the output-mode (macros vs ahkeys)
                # for ahkeys output should probably look like
                # +6 +6 +6
                # rather than
                # +{6 3}
                # only because the former is easier to
                # express in a template form easily modifiable
                # by an end user
                # might be best to use this template style:
                    # jump_begin: '{Shift down}'
                    # jump_step: '[key]'
                    # jump_end: '{Shift up}'
                if jumps > 0:
                    keys.append("{Shift down}")
                    keys.extend(keycode * jumps)
                    keys.append("{Shift up}")
                #keys.append("+{%s %d}" % (keycode[0], jumps))

        return keys

    def setsize_standard(self, start, end):
        """
        Standard sizing mechanism for dig, place, query buildtypes.
        Returns keys, newpos:
            keys needed to make the currently-designating area the correct size
            pos is where the cursor ends up after sizing the area
        """
        return self.move(start, end), end

    def setsize_build(self, start, end):
        """
        Standard sizing mechanism for the build buildtype.
        Returns keys, pos:
            keys needed to make the currently-designating area the correct size
            pos is where the cursor ends up after sizing the area
        """
        # move cursor halfway to end from start
        midpoint = start.midpoint(end)
        keys = self.move(start, midpoint)

        # resize construction
        area = Area(start, end)
        keys += KEY_LIST['[widen]'] * (area.width() - 1)
        keys += KEY_LIST['[heighten]'] * (area.height() - 1)

        return keys, midpoint

    def setsize_fixed(self, start, end):
        """
        Sizing mechanism for fixed size buildings like 3x3 workshops,
        5x5 trade depots and 5x5 siege workshops. Here we just move to
        the center of the building and deploy it. This allows for e.g.
        a 3x3 grid of 'wc' cells indicating a single carpenter's workshop.
        Returns keys, pos:
            keys needed to make the currently-designating area the correct size
            pos is where the cursor ends up after sizing the area
        """
        # move cursor halfway to end from start
        midpoint = start.midpoint(end)
        keys = self.move(start, midpoint)

        return keys, midpoint

    def setmats(self, areasize):
        """
        Tries to avoid running out of a given material type by blithely
        attempting to all-select from DF's materials list repeatedly.
        qfconvert will attempt this 1+sqrt(areasize) times, which should
        be good enough most of the time.
        """
        if areasize == 1: return ['#']

        # reps = 1 + int(sqrt(areasize))
        reps = 2 * int(sqrt(areasize))
        keys = ['#', '[menudown]'] * (reps - 1)
        keys.append('#')
        # print 'setmats ' + `keys`
        return keys