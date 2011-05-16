#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# GuessIt - A library for guessing information from filenames
# Copyright (c) 2011 Nicolas Wack <wackou@gmail.com>
#
# GuessIt is free software; you can redistribute it and/or modify it under
# the terms of the Lesser GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# GuessIt is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Lesser GNU General Public License for more details.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from guessit.patterns import deleted
from guessit.textutils import clean_string
import logging

log = logging.getLogger("guessit.matchtree")



def tree_to_string(tree):
    """Return a string representation for the given tree.

    The lines convey the following information:
     - line 1: path idx
     - line 2: explicit group idx
     - line 3: group index
     - line 4: remaining info
     - line 5: meaning conveyed

    Meaning is a letter indicating what type of info was matched by this group,
    for instance 't' = title, 'f' = format, 'l' = language, etc...

    An example is the following:

    0000000000000000000000000000000000000000000000000000000000000000000000000000000000 111
    0000011111111111112222222222222233333333444444444444444455555555666777777778888888 000
    0000000000000000000000000000000001111112011112222333333401123334000011233340000000 000
    __________________(The.Prestige).______.[____.HP.______.{__-___}.St{__-___}.Chaps].___
    xxxxxttttttttttttt               ffffff  vvvv    xxxxxx  ll lll     xx xxx         ccc
    [XCT].Le.Prestige.(The.Prestige).DVDRip.[x264.HP.He-Aac.{Fr-Eng}.St{Fr-Eng}.Chaps].mkv

    (note: the last line representing the filename is not pat of the tree representation)
    """
    m_tree = [ '', # path level index
               '', # explicit group index
               '', # matched regexp and dash-separated
               '', # groups leftover that couldn't be matched
               '', # meaning conveyed: E = episodenumber, S = season, ...
               ]

    def add_char(pidx, eidx, gidx, remaining, meaning = None):
        nr = len(remaining)
        def to_hex(x):
            if isinstance(x, int):
                return str(x) if x < 10 else chr(55+x)
            return x
        m_tree[0] = m_tree[0] + to_hex(pidx) * nr
        m_tree[1] = m_tree[1] + to_hex(eidx) * nr
        m_tree[2] = m_tree[2] + to_hex(gidx) * nr
        m_tree[3] = m_tree[3] + remaining
        m_tree[4] = m_tree[4] + str(meaning or ' ') * nr

    def meaning(result):
        mmap = { 'episodeNumber': 'E',
                 'season': 'S',
                 'extension': 'e',
                 'format': 'f',
                 'language': 'l',
                 'videoCodec': 'v',
                 'website': 'w',
                 'container': 'c',
                 'series': 'T',
                 'title': 't'
                 }

        if result is None:
            return ' '

        for prop, l in mmap.items():
            if prop in result:
                return l

        return 'x'

    for pidx, pathpart in enumerate(tree):
        for eidx, explicit_group in enumerate(pathpart):
            for gidx, (group, remaining, result) in enumerate(explicit_group):
                add_char(pidx, eidx, gidx, remaining, meaning(result))

        # special conditions for the path separator
        if pidx < len(tree) - 2:
            add_char(' ', ' ', ' ', '/')
        elif pidx == len(tree) - 2:
            add_char(' ', ' ', ' ', '.')

    return '\n'.join(m_tree)



def iterate_groups(match_tree):
    """Iterate over all the groups in a match_tree and return them as pairs
    of (group_pos, group) where:
     - group_pos = (pidx, eidx, gidx)
     - group = (string, remaining, guess)
    """
    for pidx, pathpart in enumerate(match_tree):
        for eidx, explicit_group in enumerate(pathpart):
            for gidx, group in enumerate(explicit_group):
                yield (pidx, eidx, gidx), group


def find_group(match_tree, prop):
    """Find the list of groups that resulted in a guess that contains the
    asked property."""
    result = []
    for gpos, (string, remaining, guess) in iterate_groups(match_tree):
        if guess and prop in guess:
            result.append(gpos)
    return result

def get_group(match_tree, gpos):
    pidx, eidx, gidx = gpos
    return match_tree[pidx][eidx][gidx]


def leftover_valid_groups(match_tree, valid = lambda s: len(s) > 3):
    """Return the list of valid string groups (eg: len(s) > 3) that could not be
    matched to anything as a list of pairs (cleaned_str, group_pos)."""
    leftover = []
    for gpos, (group, remaining, guess) in iterate_groups(match_tree):
        if not guess:
            clean_str = clean_string(remaining)
            if valid(clean_str):
                leftover.append((clean_str, gpos))

    return leftover


def match_from_epnum_position(match_tree, epnum_pos, guessed):
    """guessed is a callback function to call with the guessed group."""
    pidx, eidx, gidx = epnum_pos

    def update_found(leftover, group_pos, guess):
        pidx, eidx, gidx = group_pos
        group = match_tree[pidx][eidx][gidx]
        match_tree[pidx][eidx][gidx] = (group[0],
                                        deleted * len(group[0]),
                                        guess)
        return [ g for g in leftover if g[1] != group_pos ]

    # a few helper functions to be able to filter using high-level semantics
    def same_pgroup_before(group):
        _, (ppidx, eeidx, ggidx) = group
        return ppidx == pidx and (eeidx, ggidx) < (eidx, gidx)

    def same_pgroup_after(group):
        _, (ppidx, eeidx, ggidx) = group
        return ppidx == pidx and (eeidx, ggidx) > (eidx, gidx)

    def same_egroup_before(group):
        _, (ppidx, eeidx, ggidx) = group
        return ppidx == pidx and eeidx == eidx and ggidx < gidx

    def same_egroup_after(group):
        _, (ppidx, eeidx, ggidx) = group
        return ppidx == pidx and eeidx == eidx and ggidx > gidx

    leftover = leftover_valid_groups(match_tree)

    # if we only have 1 valid group before the episodeNumber, then it's probably the series name
    series_candidates = filter(same_pgroup_before, leftover)
    if len(series_candidates) == 1:
        guess = guessed({ 'series': series_candidates[0][0] }, confidence = 0.7)
        leftover = update_found(leftover, series_candidates[0][1], guess)

    # only 1 group after (in the same explicit group) and it's probably the episode title
    title_candidates = filter(same_egroup_after, leftover)
    if len(title_candidates) == 1:
        guess = guessed({ 'title': title_candidates[0][0] }, confidence = 0.5)
        leftover = update_found(leftover, title_candidates[0][1], guess)

    # epnumber is the first group and there are only 2 after it in same path group
    #  -> season title - episode title
    already_has_title = (find_group(match_tree, 'title') != [])

    title_candidates = filter(same_pgroup_after, leftover)
    if (not already_has_title and                    # no title
        not filter(same_pgroup_before, leftover) and # no groups before
        len(title_candidates) == 2):                 # only 2 groups after

        guess = guessed({ 'series': title_candidates[0][0] }, confidence = 0.4)
        leftover = update_found(leftover, title_candidates[0][1], guess)
        guess = guessed({ 'title': title_candidates[1][0] }, confidence = 0.4)
        leftover = update_found(leftover, title_candidates[1][1], guess)


    # if we only have 1 remaining valid group in the pathpart before the filename,
    # then it's probably the series name
    series_candidates = [ group for group in leftover if group[1][0] == pidx-1 ]
    if len(series_candidates) == 1:
        guess = guessed({ 'series': series_candidates[0][0] }, confidence = 0.7)
        leftover = update_found(leftover, series_candidates[0][1], guess)

    return match_tree



