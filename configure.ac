-*- mode: m4 -*-

dnl initialize autoconf
dnl when going to/from release please remove/add the nano (fourth number)
dnl releases only do Wall, cvs and prerelease does Werror too
AC_INIT(flumotion-dvb, m4_esyscmd([ test -z "$VERSION" && VERSION=0.11.0.1;
                       common/version-gen $VERSION .tarball-version]),
   [flumotion-devel@lists.fluendo.com],
   [flumotion-dvb], [http://www.flumotion.net/])

dnl initialize automake
AM_INIT_AUTOMAKE([-Wno-portability])

dnl define PACKAGE_VERSION_* variables
AS_VERSION
AC_SUBST(PACKAGE_VERSION_SPEC, `echo $VERSION | tr '-' '_'`)
AS_NANO

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(FLU_REQ, 0.10.0)

dnl Start date used to autogenrate ChangeLog from 'git log'
AC_SUBST(GIT_LOG_START_COMMIT, "3b30603ea024deb63200d9a5b2b75bcd68c26594")

dnl Add parameters for aclocal
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4 -I common")
AC_CONFIG_MACRO_DIR([m4])

dnl set up gettext
dnl the version check needs to stay here because autopoint greps for it
AM_GNU_GETTEXT_VERSION([0.11.5])
AM_GNU_GETTEXT([external])

GETTEXT_PACKAGE=$PACKAGE
AC_SUBST(GETTEXT_PACKAGE)

AS_AC_EXPAND(LIBDIR, $libdir)
AC_MSG_NOTICE(Storing library files in $LIBDIR)

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

dnl check for python
AS_PATH_PYTHON(2.3)
dnl useful when we compile our own python modules
dnl AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

dnl check for epydoc
AC_CHECK_PROG(EPYDOC, epydoc, yes, no)
AM_CONDITIONAL(HAVE_EPYDOC, test "x$EPYDOC" = "xyes")

dnl check for pychecker
AC_CHECK_PROG(PYCHECKER, pychecker, yes, no)
AM_CONDITIONAL(HAVE_PYCHECKER, test "x$PYCHECKER" = "xyes")

dnl check for flumotion
PKG_CHECK_MODULES(FLUMOTION, flumotion >= $FLU_REQ)
FLUMOTION_DIR="`$PKG_CONFIG --variable=flumotiondir flumotion`"
AC_MSG_NOTICE([Flumotion code base directory is $FLUMOTION_DIR])
AC_SUBST(FLUMOTION_DIR)

PREAMBLE=`cat $srcdir/misc/preamble.py`

dnl output stuff
FLUMOTION_SETUP(flumotion/test/setup.py, $FLUMOTION_DIR, $PREAMBLE, dvb)
FLUMOTION_SETUP(misc/setup.py, $FLUMOTION_DIR, $PREAMBLE, dvb)

AC_CONFIG_FILES([env], [chmod +x env])

dnl output stuff
AC_OUTPUT(
Makefile
common/Makefile
flumotion/Makefile
flumotion/test/Makefile
flumotion/component/Makefile
flumotion/component/producers/Makefile
flumotion/component/producers/dvb/Makefile
flumotion/project/Makefile
flumotion/project/dvb.py
flumotion/worker/checks/Makefile
flumotion/worker/Makefile
misc/Makefile
flumotion-dvb.spec
po/Makefile.in
)
