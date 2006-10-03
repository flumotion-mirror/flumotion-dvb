# -*- Mode: Python; test-case-name: flumotion.test.test_sample_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

__values = {
    0: (False, False),
    2: (True, True),
    4: (True, False),
    5: (False, True),
}

def getBooleans(method):
    # convert a method number to a hor, ver boolean tuple
    return __values[method]

def getMethod(horizontal, vertical):
    for m, t in __values.items():
        if t == (horizontal, vertical):
            return m

    raise IndexError
