#  Copyright (c) 2011, Karl Gyllstrom
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met: 
#
#  1. Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer. 
#  2. Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution. 
#  
#     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#     ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#     WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#     DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#     ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#     (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#     LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#     ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#     (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#     SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#  
#     The views and conclusions contained in the software and documentation are those
#     of the authors and should not be interpreted as representing official policies, 
#     either expressed or implied, of the FreeBSD Project.


from blargs import Parser, Option, ConflictError, ArgumentError,\
                   DependencyError, MissingRequiredArgumentError,\
                   FormatError, ConditionError,\
                   MultipleSpecifiedArgumentError,\
                   ManyAllowedNoneSpecifiedArgumentError,\
                   MissingValueError, FailedConditionError,\
                   FakeSystemExit


import sys
import os
from itertools import permutations
import unittest


if sys.version_info[0] == 3:
    import functools
    reduce = functools.reduce
    xrange = range
    import io
    StringIO = io.StringIO
else:
    from StringIO import StringIO


class FileBasedTestCase(unittest.TestCase):
    def setUp(self):
        from tempfile import mkdtemp
        self._dir = mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._dir)

    def test_config(self):
        p = Parser({})
        p.config('a')
        self.assertRaises(IOError, p._process_command_line, ['--a', 'doesnotexist.cfg'])
        fname = os.path.join(self._dir, 'config.cfg')

        def write_config(**kw):
            delim = '='
            if 'delim' in kw:
                delim = kw['delim']
                del kw['delim']
            with open(fname, 'w') as w:
                w.write('[myconfig]\n# comment1\n; comment2\n' + '\n'.join(
                    ('%s %s %s' % (k, delim, v) for k, v in kw.items())))

        write_config(b=3, c='hello')

        vals = p._process_command_line(['--a', fname])
        self.assertEqual(list(vals.keys()), ['help'])

        write_config(b=3, c='hello', d='what')

        p = Parser({})
        p.config('a')
        p.int('b')
        p.str('c')
        p.int('d')

        self.assertRaises(FormatError, p._process_command_line, ['--a', fname])

        write_config(b=3, c='hello', d=5)

        vals = p._process_command_line(['--a', fname])
        self.assertEqual(vals['b'], 3)
        self.assertEqual(vals['c'], 'hello')
        self.assertEqual(vals['d'], 5)

        vals = p._process_command_line(['--a', fname, '--d', '4'])
        self.assertEqual(vals['b'], 3)
        self.assertEqual(vals['c'], 'hello')
        self.assertEqual(vals['d'], 4)

        vals = p._process_command_line(['--a', fname, '--d', '4', '--c', 'sup',
            '--b', '1'])

        self.assertEqual(vals['b'], 1)
        self.assertEqual(vals['c'], 'sup')
        self.assertEqual(vals['d'], 4)

        p = Parser({})
        p.config('a')
        p.int('b').requires(p.int('d'))
        p.str('c')
        write_config(b=3, c='sup')
        self.assertRaises(DependencyError, p._process_command_line, ['--a',
            fname])

        write_config(b=3, c='sup', delim=':')
        vals = p._process_command_line(['--a', fname, '--d', '4', '--c', 'sup',
            '--b', '1'])

        self.assertEqual(vals['b'], 1)
        self.assertEqual(vals['c'], 'sup')
        self.assertEqual(vals['d'], 4)

    def test_file(self):
        p = Parser(locals())
        p.file('a')
        self.assertRaises(MissingValueError, p._process_command_line, ['--a'])
        self.assertRaises(IOError, p._process_command_line, ['--a', 'aaa'])
        vals = p._process_command_line(['--a', 'test.py'])
        with open('test.py') as f:
            self.assertEqual(vals['a'].read(), f.read())

        p = Parser(locals())
        p.file('a', mode='w')
        fname = os.path.join(self._dir, 'mytest')
        vals = p._process_command_line(['--a', fname])
        f = vals['a']
        msg = 'aaaxxx'
        f.write(msg)
        f.close()

        with open(fname) as f:
            self.assertEqual(f.read(), msg)

    def test_directory(self):
        p = Parser(locals())
        p.directory('a')
        dirpath = os.path.join(self._dir, 'ok')
        self.assertRaises(IOError, p._process_command_line, ['--a', dirpath])
        os.mkdir(dirpath)
        vals = p._process_command_line(['--a', dirpath])
        self.assertEqual(vals['a'], dirpath)

        # fail when trying to indicate directory that is actually a file
        fname = os.path.join(self._dir, 'testfile')
        with open(fname, 'w') as f:
            f.write('mmm')
        self.assertRaises(IOError, p._process_command_line, ['--a', fname])

        # create directory
        dirpath = os.path.join(self._dir, 'sub', 'leaf')
        p.directory('b', create=True)
        vals = p._process_command_line(['--b', dirpath])
        self.assertEqual(vals['b'], dirpath)


class TestCase(unittest.TestCase):
    def test_env(self):
        import os

        os.environ['PORT'] = 'yes'
        p = Parser()
        p.int('port').environment()

        self.assertRaises(FormatError, p._process_command_line)

        os.environ['PORT'] = '9999'

        for port in ('Port', 'pORt', 'port', 'PORT'):
            p = Parser()
            p.int(port).environment()
            vals = p._process_command_line()
            self.assertEqual(vals[port], 9999)

            vals = p._process_command_line(['--%s' % port, '2222'])
            self.assertEqual(vals[port], 2222)

    def test_error_printing(self):
        def create(strio):
            with Parser(locals()) as p:
                p._out = strio
                p._suppress_sys_exit = True
                p.require_one(
                    p.all_if_any(
                        p.int('a'),
                        p.int('b'),
                    ),
                    p.only_one_if_any(
                        p.int('c'),
                        p.int('d'),
                    )
                )
                p.int('x').required()
                p.str('yi').shorthand('y')
                p.float('z').multiple()
                p.range('e')

        s = StringIO()
        self.assertRaises(FakeSystemExit, create, s)
        self.assertEqual(s.getvalue(), '''Error: [--a, --b, --c, --d] not specified
usage: {0}
[--a <int>] [--yi/-y <option>] [--c <int>] [--b <int>] [--e <range>] [--help/-h] [--x <int>] [--z <float>] [--d <int>]
'''.format(sys.argv[0]))

    def test_url(self):
        p = Parser()
        p.url('url')
        vals = p._process_command_line(['--url', 'http://www.com'])
        self.assertRaises(FormatError, p._process_command_line, ['--url', '/www.com'])


    def test_non_arg_exception(self):
        def inner():
            with Parser() as p:
                p.flag()

        self.assertRaises(TypeError, inner)

    def test_requires_and_default(self):
        p = Parser()
        p.int('a').default(3)
        p.flag('b').requires(p['a'])
        p._process_command_line(['--b'])

    def test_complex1(self):
        p = Parser()
        p.require_one(
            p.all_if_any(
                p.int('a'),
                p.int('b'),
                p.int('c'),
            ),
            p.only_one_if_any(
                p.int('d'),
                p.int('e'),
                p.int('f'),
            ),
        )

        self.assertRaises(ArgumentError, p._process_command_line)
        p._process_command_line(['--d', '3'])
        p._process_command_line(['--e', '3'])
        p._process_command_line(['--f', '3'])
        self.assertRaises(ConflictError, p._process_command_line, ['--d', '3', '--e', '4'])

        self.assertRaises(DependencyError, p._process_command_line, ['--a', '3'])
        self.assertRaises(DependencyError, p._process_command_line, ['--b', '3'])
        self.assertRaises(DependencyError, p._process_command_line, ['--c', '3'])

        p._process_command_line(['--a', '3', '--b', '4', '--c', '5'])
        self.assertRaises(ConflictError, p._process_command_line, ['--a', '3',
            '--b', '4', '--c', '5', '--d', '3'])

    def test_complex2(self):
        p = Parser()
        p.require_one(
            p.all_if_any(
                p.only_one_if_any(
                    p.flag('a'),
                    p.flag('b'),
                ),
                p.flag('c'),
            ),
            p.only_one_if_any(
                p.all_if_any(
                    p.flag('d'),
                    p.flag('e'),
                ),
                p.flag('f'),
            ),
        )

        satisfies1 = (['--a', '--c'], ['--b', '--c'])
        self.assertRaises(DependencyError, p._process_command_line, ['--a'])
        self.assertRaises(DependencyError, p._process_command_line, ['--b'])
        self.assertRaises(DependencyError, p._process_command_line, ['--c'])
        self.assertRaises(ConflictError, p._process_command_line, ['--a', '--b', '--c'])

        satisfies2 = (['--d', '--e'], ['--f'])
        self.assertRaises(ArgumentError, p._process_command_line)
        self.assertRaises(DependencyError, p._process_command_line, ['--d'])
        p._process_command_line(['--d', '--e'])
        self.assertRaises(ConflictError, p._process_command_line, ['--d',
            '--e', '--f'])
        p._process_command_line(['--f'])

        for s1 in satisfies1:
            p._process_command_line(s1)
            for s2 in satisfies2:
                self.assertRaises(ConflictError, p._process_command_line, s1 + s2)

        for s2 in satisfies2:
            p._process_command_line(s1)

    def test_numeric_conditions(self):
        p = Parser()
        a = p.float('a')
        p.int('b').unless(a < 20)
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '20'])
        p._process_command_line(['--a', '19'])
        p._process_command_line(['--a', '9'])
        p._process_command_line(['--b', '3', '--a', '29'])

        p.int('c').unless(10 < a)
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '20'])
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '9'])
        p._process_command_line(['--a', '19'])

        d = p.int('d').unless(a == 19)
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '20'])
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '9'])
        p._process_command_line(['--a', '19'])

        e = p.int('e').unless(a == d)
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '19'])
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, ['--a', '19', '--d', '18'])
        p._process_command_line(['--a', '19', '--d', '19'])

        p.int('f').unless(e != d)
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '19'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '19', '--d', '18'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '19', '--d', '19', '--e',
                    '19'])

        p._process_command_line(['--a', '19', '--d', '19', '--e', '18'])

        p = Parser()
        a = p.float('a')
        b = p.float('b').requires(a < 10)
        self.assertRaises(ConditionError, p._process_command_line, ['--b',
            '3.9', '--a', '11'])

        p = Parser()
        a = p.float('a')
        b = p.float('b').if_(a < 10)
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '8'])

        p._process_command_line(['--a', '11'])

    def test_conditions(self):
        p = Parser()
        a = p.float('a')
        b = p.float('b')
        c = p.float('c').requires(a.or_(b))
        self.assertRaises(DependencyError, p._process_command_line, ['--c', '9.2'])
        p._process_command_line(['--a', '11', '--c', '9.2'])
        p._process_command_line(['--b', '11', '--c', '9.2'])

        p = Parser()
        a = p.float('a')
        b = p.float('b')
        c = p.float('c').if_(a.or_(b))
        p._process_command_line(['--c', '9.2'])
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '11'])

        p._process_command_line(['--a', '11', '--c', '9.2'])
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--b', '11'])

        p._process_command_line(['--b', '11', '--c', '9.2'])

    def test_compound(self):
        p = Parser()
        a = p.float('a')
        b = p.float('b').unless((a > 0).and_(a < 10))
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '0'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '10'])

        p._process_command_line(['--a', '5'])

        p = Parser()
        a = p.float('a')
        c = p.float('b').unless((a < 0).or_(a > 10))
        p._process_command_line(['--a', '11'])
        p._process_command_line(['--a', '-1'])
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '0'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '10'])

        p = Parser()
        a = p.float('a')
        c = p.float('b').if_(a > 0).unless((a > 10).and_(a < 20))
        p._process_command_line(['--a', '11'])
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '1'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '5'])

        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, ['--a', '20'])

        p = Parser()
        a = p.flag('a')
        b = p.flag('b')
        p.flag('c').requires(a.or_(b))
        p.flag('d').requires(a.and_(b))

        self.assertRaises(DependencyError, p._process_command_line, ['--c'])
        p._process_command_line(['--c', '--a'])
        p._process_command_line(['--c', '--b'])
        p._process_command_line(['--c', '--a', '--b'])
        self.assertRaises(DependencyError, p._process_command_line, ['--d'])
        self.assertRaises(DependencyError, p._process_command_line, ['--d', '--a'])
        self.assertRaises(DependencyError, p._process_command_line, ['--d', '--b'])
        p._process_command_line(['--d', '--a', '--b'])

    def test_redundant(self):
        try:
            with Parser() as p:
                p.float('a')
                p.int('a')
            self.fail()
        except ValueError:
            pass

    def test_groups(self):
        p = Parser()
        p.require_one(
            p.only_one_if_any(
                p.flag('a'),
                p.flag('b')
            ),
            p.only_one_if_any(
                p.flag('c'),
                p.flag('d')
            )
        )

        self.assertRaises(ManyAllowedNoneSpecifiedArgumentError, p._process_command_line, [])
        p._process_command_line(['--a'])
        p._process_command_line(['--b'])
        for char in 'abcd':
            for other in set('abcd') - set([char]):
                self.assertRaises(ConflictError, p._process_command_line, ['--%s' % char, '--%s' % other])

        p = Parser()
        p.only_one_if_any(
            p.flag('a'),
            p.flag('b')
        ).requires(
            p.only_one_if_any(
                p.flag('c'),
                p.flag('d')
            )
        )

        self.assertRaises(DependencyError, p._process_command_line, ['--a'])
        self.assertRaises(DependencyError, p._process_command_line, ['--b'])
        p._process_command_line(['--c'])
        p._process_command_line(['--d'])

        p._process_command_line(['--a', '--c'])
        p._process_command_line(['--b', '--c'])
        p._process_command_line(['--a', '--d'])
        p._process_command_line(['--b', '--d'])

    def test_float(self):
        p = Parser()
        p.float('a')
        p.float('c')
        self.assertRaises(FormatError, p._process_command_line, ['--a', 'b'])
        self.assertRaises(FormatError, p._process_command_line, ['--a', '1.2.3'])
        self.assertRaises(MissingValueError, p._process_command_line, ['--a'])
#        p._process_command_line(['--a', '--b'])  # XXX what shoudl correct behavior be?

    def test_errors(self):
        p = Parser()
        p.int('a')
        try:
            p._process_command_line([])
        except TypeError:
            self.fail()

    def test_condition(self):
        p = Parser()
        p.str('a').condition(lambda x: x['b'] != 'c')
        p.str('b')

        p._process_command_line(['--a', '1', '--b', 'b'])
        self.assertRaises(FailedConditionError, p._process_command_line, ['--a', '1', '--b', 'c'])

    def test_localize(self):
        p = Parser.with_locals()
        p.str('multi-word').requires(p.str('another-multi-word'))
        vals = p._process_command_line(['--multi-word', 'a', '--another-multi-word', 'b'])
        self.assertTrue('multi_word' in vals)
        self.assertFalse('multi-word' in vals)
        self.assertTrue('multi_word' in locals())

    def test_multiword(self):
        p = Parser()
        p.multiword('aa')
        p.str('ab')

        self.assertRaises(MissingValueError, p._process_command_line, ['--aa'])
        vals = p._process_command_line(['--aa', 'a', '--ab', 'b'])
        self.assertEqual(vals['aa'], 'a')
        self.assertEqual(vals['ab'], 'b')

        vals = p._process_command_line(['--aa', 'a c d', '--ab', 'b'])
        self.assertEqual(vals['aa'], 'a c d')

        vals = p._process_command_line(['--aa', 'a', 'c', 'd', '--ab', 'b'])
        self.assertEqual(vals['aa'], 'a c d')

        p = Parser().set_single_prefix('+').set_double_prefix('M')
        p.multiword('aa')
        p.str('ab').shorthand('a')
        vals = p._process_command_line(['Maa', 'a', 'c', 'd', 'Mab', 'b'])
        self.assertEqual(vals['aa'], 'a c d')
        vals = p._process_command_line(['Maa', 'a', 'c', 'd', '+a', 'b'])
        self.assertEqual(vals['aa'], 'a c d')

        self.assertRaises(ValueError, Parser().set_single_prefix('++').set_double_prefix, '+')

    def test_shorthand(self):
        p = Parser()
        aa = p.int('aa').shorthand('a')
        self.assertRaises(ValueError, lambda x: p.int('ab').shorthand(x), 'a')
        self.assertRaises(ValueError, p.int('bb').shorthand, 'a')
        self.assertRaises(ValueError, aa.shorthand, 'a')
#        self.assertRaises(ValueError, aa.shorthand, 'b')

    def test_range(self):
        def create():
            l = {}
            p = Parser(l)
            x = p.range('arg').shorthand('a')
            self.assertTrue(x is not None)
            return p, l

        def xrange_equals(x1, x2):
            return list(x1) == list(x2)

        p, l = create()
        self.assertRaises(MissingValueError, p._process_command_line, ['--arg'])
        p._process_command_line(['--arg', '1:2'])
        self.assertTrue(xrange_equals(l['arg'], xrange(1, 2)))

        p, l = create()
        self.assertRaises(FormatError, p._process_command_line, ['--arg', '1:s2'])

        p, l = create()
        p._process_command_line(['--arg', '1:-1'])
        self.assertTrue(xrange_equals(l['arg'], xrange(1, 1)))

        v = p._process_command_line(['--arg', '0', '9'])
        self.assertTrue(xrange_equals(v['arg'], xrange(0, 9)))

        v = p._process_command_line(['--arg', '9'])
        self.assertTrue(xrange_equals(v['arg'], xrange(9)))

        v = p._process_command_line(['--arg', '0', '9', '3'])
        self.assertTrue(xrange_equals(v['arg'], xrange(0, 9, 3)))

        p.set_single_prefix('+')
        v = p._process_command_line(['+a', '0', '-1', '3'])
        self.assertTrue(xrange_equals(v['arg'], xrange(0, -1, 3)))

    def test_multiple(self):
        p = Parser()
        p.str('x')

        self.assertRaises(MultipleSpecifiedArgumentError,
                p._process_command_line, ['--x', '1', '--x', '2'])

        p = Parser()
        x = p.str('x').multiple()
        self.assertTrue(x != None)

        p._process_command_line(['--x', '1', '--x', '2'])

    def test_unspecified_default(self):
        p = Parser({})
        p.str('x').unspecified_default()
        self.assertRaises(ValueError, Option.unspecified_default, p.str('y'))

        vals = {}
        p = Parser(vals)
        p.str('x').unspecified_default().required()
        p._process_command_line(['ok'])
        self.assertEqual(vals['x'], 'ok')

        p = Parser({})
        p.str('x').unspecified_default().conflicts(p.str('y'))
        self.assertRaises(ConflictError, p._process_command_line,
            ['--y', 'a', 'unspecified_default'])

        p = Parser({})
        p.str('x').unspecified_default().conflicts(p.str('y'))
        self.assertRaises(ConflictError, p._process_command_line,
            ['unspecified_default', '--y', 'a'])

        # multiple
        p = Parser()
        p.str('x').unspecified_default()
        self.assertRaises(ValueError, p.str('y').unspecified_default)
    
    def test_with(self):
        import sys
        sys.argv[1:] = ['--x', 'yes']
        d = {'test_x': None}

        p = Parser(d)
        with p:
            p.str('x').shorthand('test-x')

    def test_bad_format(self):
        p = Parser()
        p.str('f')
        p.str('m')

        # This no longer fails because (I think) -m is a value for -m, and x
        # being extra is now ok
        # self.assertRaises(ArgumentError, p._process_command_line, '-f -m x'.split())

    def test_basic(self):
        p = Parser()
        p.str('x')
        p.flag('y')
        vals = p._process_command_line([])
        self.assertTrue(vals['x'] is None)
#        self.assertEqual(vals['x'], x)
#        self.assertEqual(vals['y'], y)
        self.assertFalse(vals['y'])

    def test_add(self):
        p = Parser()
        p.str('x')
        vals = p._process_command_line(['--x', 'hi'])
        self.assertEqual(vals['x'], 'hi')

        p = Parser(locals())
        p.str('x')
        p._process_command_line(['--x', 'hi'])
        self.assertTrue('x' in locals())

        p = Parser()
        p.str('x')
        vals = p._process_command_line(['--x=5'])
        self.assertEqual(vals['x'], '5')

    def test_default(self):
        p = Parser()
        p.int('x').default(5)
        vals = p._process_command_line([])
        self.assertEqual(vals['x'], 5)

        p = Parser()
        p.int('x').default(5)
        vals = p._process_command_line(['--x', '6'])
        self.assertEqual(vals['x'], 6)
    
    def test_cast(self):
        p = Parser()
        p.str('x').cast(int)
        vals = p._process_command_line(['--x', '1'])
        self.assertEqual(vals['x'], 1)
        self.assertRaises(ArgumentError, p._process_command_line, ['--x', 'a'])

        p = Parser()
        p.int('x')
        vals = p._process_command_line(['--x', '1'])

        p = Parser()
        p.multiword('x').cast(lambda x: [float(y) for y in x.split()])
        vals = p._process_command_line(['--x', '1.2 9.8 4.6'])
        self.assertEqual(vals['x'], [1.2, 9.8000000000000007,
            4.5999999999999996])

        p = Parser()
        p.int('x').default('yes')
        self.assertRaises(FormatError, p._process_command_line)

    def test_required(self):
        p = Parser()
        p.str('x').required()
        self.assertRaises(MissingRequiredArgumentError, p._process_command_line, [])

        p = Parser()
        p.str('x').required()
        self.assertRaises(MissingRequiredArgumentError,
                p._process_command_line, [])

        p = Parser()
        y = p.str('y')
        z = p.str('z')
        x = p.str('x').unless(y.or_(z))
        self.assertTrue(x != None)
        self.assertRaises(ArgumentError,
                p._process_command_line, [])
        p._process_command_line(['--y', 'a'])
        p._process_command_line(['--x', 'a'])
        p._process_command_line(['--x', 'a', '--y', 'b'])
        p._process_command_line(['--z', 'a'])

    def test_requires(self):
        p = Parser()
        r = p.str('x')
        self.assertRaises(ValueError, r.requires, 'y')
        try:
            r.requires(p.str('y'))
        except ValueError:
            self.fail()

        p = Parser()
        y = p.flag('y')
        p.flag('x').requires(y)

        self.assertRaises(DependencyError, p._process_command_line, ['--x'])

    def test_depends(self):
        def create():
            p = Parser()
            p.str('x').requires(p.str('y'))

            return p

        self.assertRaises(DependencyError, create()._process_command_line, ['--x', 'hi'])
        try:
            create()._process_command_line(['--y', 'sup'])
        except:
            self.assertTrue(False)

        try:
            create()._process_command_line(['--x', 'hi', '--y', 'sup'])
        except:
            self.assertTrue(False)

    def test_depends_group(self):
        def create():
            p = Parser()
            p.str('x').requires(
                p.str('y'),
                p.str('z'),
                p.str('w')
            )

            return p

#        o1.add_dependency_group((o2, o3, o4))

        self.assertRaises(DependencyError, create()._process_command_line, ['--x', 'hi'])
        try:
            create()._process_command_line(['--y', 'sup'])
        except:
            self.fail()

        for v in permutations([('--y', 'sup'), ('--z', 'zup'), ('--w', 'wup')], 2):
            self.assertRaises(DependencyError, create()._process_command_line,
                    ['--x', 'hi'] + reduce(list.__add__, map(list, v)))

    def test_conflicts(self):
        def create():
            p = Parser()
            p.flag('x').conflicts(p.flag('y'))
            return p

        self.assertRaises(ConflictError, create()._process_command_line, ['--x', '--y'])
        create()._process_command_line(['--y'])

        try:
            create()._process_command_line(['--x'])
        except:
            self.assertTrue(False)

    def test_mutually_exclusive(self):
        def create():
            p = Parser()
            p.flag('x')
            p.flag('y')
            p.flag('z')

            p.only_one_if_any(*'xyz')
            return p

        self.assertRaises(ConflictError, create()._process_command_line, ['--x', '--y'])
        self.assertRaises(ConflictError, create()._process_command_line, ['--x', '--z'])
        self.assertRaises(ConflictError, create()._process_command_line, ['--y', '--z'])
        self.assertRaises(ConflictError, create()._process_command_line, ['--x', '--y', '--z'])

        create()._process_command_line(['--x'])
        create()._process_command_line(['--y'])
        create()._process_command_line(['--z'])
    
    def test_mutually_dependent(self):
        def create():
            p = Parser()
            p.all_if_any(
                p.flag('x'),
                p.flag('y'),
                p.flag('z')
            )

            return p

        self.assertRaises(DependencyError, create()._process_command_line, ['--x'])
        self.assertRaises(DependencyError, create()._process_command_line, ['--y'])
        self.assertRaises(DependencyError, create()._process_command_line, ['--z'])
        self.assertRaises(DependencyError, create()._process_command_line, ['--x', '--y'])
        self.assertRaises(DependencyError, create()._process_command_line, ['--x', '--z'])
        self.assertRaises(DependencyError, create()._process_command_line, ['--y', '--z'])

        create()._process_command_line(['--x', '--y', '--z'])

    def test_oo(self):
        p = Parser()
        p.flag('x')
        p.flag('y')
        p.flag('z').requires('y')
        x = p['x']
        x.requires('y', 'z')
        self.assertRaises(DependencyError, p._process_command_line, ['--x'])
        self.assertRaises(DependencyError, p._process_command_line, ['--z'])
        p._process_command_line(['--y'])

        p = Parser()
        p.flag('x')
        p.flag('y').conflicts('x')
        self.assertRaises(ConflictError, p._process_command_line, ['--y', '--x'])

#    def test_index(self):
#        p = Parser()
#        p.str('x')
#        self.assertEqual(p['y'], None)
    
    def test_set_at_least_one_required(self):
        def create():
            p = Parser()
            p.str('x')
            p.str('y')
            p.str('z')

            p.at_least_one('x', 'y', 'z')
            return p

        create()._process_command_line(['--x', '1'])
        create()._process_command_line(['--y', '1'])
        create()._process_command_line(['--z', '1'])
        create()._process_command_line(['--x', '1', '--y', '1'])
        create()._process_command_line(['--x', '1', '--y', '1', '--z', '1'])
        create()._process_command_line(['--x', '1', '--z', '1'])
        create()._process_command_line(['--y', '1', '--z', '1'])
        self.assertRaises(ArgumentError, create()._process_command_line, [])

    def test_one_required(self):
        def create():
            p = Parser()
            p.str('x')
            p.str('y')
            p.str('z')

            p.require_one(*'xyz')
            return p

        create()._process_command_line(['--x', '1'])
        create()._process_command_line(['--y', '1'])
        create()._process_command_line(['--z', '1'])

        self.assertRaises(ConflictError, create()._process_command_line, ['--x', '1', '--y', '1'])
        self.assertRaises(ArgumentError, create()._process_command_line, [])

        p = Parser()
        p.flag('a')
        p.flag('b')
        p.require_one('a', 'b')
        p._process_command_line(['--b'])


if __name__ == '__main__':
    unittest.main()
