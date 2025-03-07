# SPDX-FileCopyrightText: 2020 - 2023 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

"""
Itanium CXX ABI Mangler

Reference: https://itanium-cxx-abi.github.io/cxx-abi/abi.html

The basics of the mangling scheme.

We are hijacking the CXX mangling scheme for our use.  We map Python modules
into CXX namespace.  A `module1.submodule2.foo` is mapped to
`module1::submodule2::foo`.   For parameterized numba types, we treat them as
templated types; for example, `array(int64, 1d, C)` becomes an
`array<int64, 1, C>`.

All mangled names are prefixed with "_Z".  It is followed by the name of the
entity.  A name contains one or more identifiers.  Each identifier is encoded
as "<num of char><name>".   If the name is namespaced and, therefore,
has multiple identifiers, the entire name is encoded as "N<name>E".

For functions, arguments types follow.  There are condensed encodings for basic
built-in types; e.g. "i" for int, "f" for float.  For other types, the
previously mentioned name encoding should be used.

For templated types, the template parameters are encoded immediately after the
name.  If it is namespaced, it should be within the 'N' 'E' marker.  Template
parameters are encoded in "I<params>E", where each parameter is encoded using
the mentioned name encoding scheme.  Template parameters can contain literal
values like the '1' in the array type shown earlier.  There is special encoding
scheme for them to avoid leading digits.
"""


import re

from numba.core import types


def mangle_type_or_value(typ):
    """
    Mangle type parameter and arbitrary value.

    This function extends Numba's `magle_type_or_value()` to
    support numba.types.CPointer type, e.g. an ``int *`` argument will be
    mangled to "Pi".
    Mangling of extended qualifiers is supported only
    for address space qualifiers. In which case, the mangling
    follows the rule defined in Section 5.1.5.1 of the ``Itanium ABI
    <https://itanium-cxx-abi.github.io/cxx-abi/abi.html#mangle.qualified-type>``_.
    For example, an ``int global *`` argument will be mangeled to "PU3AS1i".

    Args:
        typ (numba.types, int, str) : Type to mangle

    Returns:
        str: The mangled name of the type

    """
    if isinstance(typ, types.CPointer):
        rc = "P"
        if typ.addrspace is not None:
            rc += "U" + mangle_identifier("AS" + str(typ.addrspace))
        rc += mangle_type_or_value_numba(typ.dtype)
        return rc
    else:
        return mangle_type_or_value_numba(typ)


def mangle_ext(ident, argtys, *, abi_tags=()):
    """
    Mangle identifier with Numba type objects and abi-tags.
    """
    kwargs = {}

    # for support numba 0.54 and <=0.55.0dev0=*_469
    if abi_tags:
        kwargs["abi_tags"] = abi_tags

    return PREFIX + mangle_identifier(ident, **kwargs) + mangle_args(argtys)


# According the scheme, valid characters for mangled names are [a-zA-Z0-9_].
# We borrow the '_' as the escape character to encode invalid char into
# '_xx' where 'xx' is the hex codepoint.
_re_invalid_char = re.compile(r"[^a-z0-9_]", re.I)

PREFIX = "_Z"

# C names to mangled type code
C2CODE = {
    "void": "v",
    "wchar_t": "w",
    "bool": "b",
    "char": "c",
    "signed char": "a",
    "unsigned char": "h",
    "short": "s",
    "unsigned short": "t",
    "int": "i",
    "unsigned int": "j",
    "long": "l",
    "unsigned long": "m",
    "long long": "x",  # __int64
    "unsigned long long": "y",  # unsigned __int64
    "__int128": "n",
    "unsigned __int128": "o",
    "half": "Dh",
    "float": "f",
    "double": "d",
    "long double": "e",  # __float80
    "__float128": "g",
    "ellipsis": "z",
}

# Numba types to C names
N2C = {
    types.void: "void",
    types.boolean: "bool",
    types.uint8: "unsigned char",
    types.int8: "signed char",
    types.uint16: "unsigned short",
    types.int16: "short",
    types.uint32: "unsigned int",
    types.int32: "int",
    types.uint64: "unsigned long long",
    types.int64: "long long",
    types.float16: "half",
    types.float32: "float",
    types.float64: "double",
}


def _escape_string(text):
    """Escape the given string so that it only contains ASCII characters
    of [a-zA-Z0-9_$].

    The dollar symbol ($) and other invalid characters are escaped into
    the string sequence of "$xx" where "xx" is the hex codepoint of the char.

    Multibyte characters are encoded into utf8 and converted into the above
    hex format.
    """

    def repl(m):
        return "".join(("_%02x" % ch) for ch in m.group(0).encode("utf8"))

    ret = re.sub(_re_invalid_char, repl, text)
    # Return str if we got a unicode (for py2)
    if not isinstance(ret, str):
        return ret.encode("ascii")
    return ret


def _fix_lead_digit(text):
    """
    Fix text with leading digit
    """
    if text and text[0].isdigit():
        return "_" + text
    else:
        return text


def _len_encoded(string):
    """
    Prefix string with digit indicating the length.
    Add underscore if string is prefixed with digits.
    """
    string = _fix_lead_digit(string)
    return "%u%s" % (len(string), string)


def mangle_abi_tag(abi_tag: str) -> str:
    return "B" + _len_encoded(_escape_string(abi_tag))


def mangle_identifier(ident, template_params="", *, abi_tags=(), uid=None):
    """
    Mangle the identifier with optional template parameters and abi_tags.

    Note:

    This treats '.' as '::' in C++.
    """
    parts = [_len_encoded(_escape_string(x)) for x in ident.split(".")]
    enc_abi_tags = list(map(mangle_abi_tag, abi_tags))
    extras = template_params + "".join(enc_abi_tags)
    if len(parts) > 1:
        return "N%s%sE" % ("".join(parts), extras)
    else:
        return "%s%s" % (parts[0], extras)


def mangle_type_c(typ):
    """
    Mangle C type name

    Args
    ----
    typ: str
        C type name
    """
    if typ in C2CODE:
        return C2CODE[typ]
    else:
        return mangle_identifier(typ)


def mangle_type_or_value_numba(typ):
    """
    Mangle type parameter and arbitrary value.
    """
    # Handle numba types
    if isinstance(typ, types.Type):
        if typ in N2C:
            return mangle_type_c(N2C[typ])
        else:
            return mangle_templated_ident(*typ.mangling_args)
    # Handle integer literal
    elif isinstance(typ, int):
        return "Li%dE" % typ
    # Handle str as identifier
    elif isinstance(typ, str):
        return mangle_identifier(typ)
    # Otherwise
    else:
        enc = _escape_string(str(typ))
        return _len_encoded(enc)


# Alias
mangle_type = mangle_type_or_value
mangle_value = mangle_type_or_value


def mangle_templated_ident(identifier, parameters):
    """
    Mangle templated identifier.
    """
    template_params = (
        "I%sE" % "".join(map(mangle_type_or_value, parameters))
        if parameters
        else ""
    )
    return mangle_identifier(identifier, template_params)


def mangle_args_c(argtys):
    """
    Mangle sequence of C type names
    """
    return "".join([mangle_type_c(t) for t in argtys])


def mangle_args(argtys):
    """
    Mangle sequence of Numba type objects and arbitrary values.
    """
    return "".join([mangle_type_or_value(t) for t in argtys])


def mangle_c(ident, argtys):
    """
    Mangle identifier with C type names
    """
    return PREFIX + mangle_identifier(ident) + mangle_args_c(argtys)


def mangle(ident, argtys, *, abi_tags=(), uid=None):
    """
    Mangle identifier with Numba type objects and abi-tags.
    """
    return "".join(
        [
            PREFIX,
            mangle_identifier(ident, abi_tags=abi_tags, uid=uid),
            mangle_args(argtys),
        ]
    )


def prepend_namespace(mangled, ns):
    """
    Prepend namespace to mangled name.
    """
    if not mangled.startswith(PREFIX):
        raise ValueError("input is not a mangled name")
    elif mangled.startswith(PREFIX + "N"):
        # nested
        remaining = mangled[3:]
        ret = PREFIX + "N" + mangle_identifier(ns) + remaining
    else:
        # non-nested
        remaining = mangled[2:]
        head, tail = _split_mangled_ident(remaining)
        ret = PREFIX + "N" + mangle_identifier(ns) + head + "E" + tail
    return ret


def _split_mangled_ident(mangled):
    """
    Returns `(head, tail)` where `head` is the `<len> + <name>` encoded
    identifier and `tail` is the remaining.
    """
    ct = int(mangled)
    ctlen = len(str(ct))
    at = ctlen + ct
    return mangled[:at], mangled[at:]
