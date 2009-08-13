# Copyright (C) 2009 by Eric Talevich (eric.talevich@gmail.com)
# This code is part of the Biopython distribution and governed by its
# license. Please see the LICENSE file that should have been included
# as part of this package.

"""PhyloXML reader/parser, writer, and associated functions.

Instantiates Tree elements from a parsed PhyloXML file, and constructs an XML
file from a Tree.PhyloXML object.
"""
__docformat__ = "epytext en"

import sys
import warnings

from Bio.Tree import PhyloXML as Tree

try:
    from xml.etree import cElementTree as ElementTree
except ImportError:
    try:
        from xml.etree import ElementTree as ElementTree
    except ImportError:
        # Python 2.4 -- check for 3rd-party implementations
        try:
            from lxml.etree import ElementTree
        except ImportError:
            try:
                import cElementTree as ElementTree
            except ImportError:
                try:
                    from elementtree import ElementTree
                except ImportError:
                    from Bio import MissingExternalDependencyError
                    raise MissingExternalDependencyError(
                            "No ElementTree module was found. "
                            "Use Python 2.5+, lxml or elementtree if you "
                            "want to use Bio.PhyloXML.")

# Keep the standard namespace prefixes when writing
# See http://effbot.org/zone/element-namespaces.htm
NAMESPACES = {
        'phy':  'http://www.phyloxml.org',
        'xs':   'http://www.w3.org/2001/XMLSchema',
        }

try:
    register_namespace = ElementTree.register_namespace
except AttributeError:
    if not hasattr(ElementTree, '_namespace_map'):
        # cElementTree needs the pure-Python xml.etree.ElementTree
        # Py2.4 support: the exception handler can go away when Py2.4 does
        try:
            from xml.etree import ElementTree as ET_py
            ElementTree._namespace_map = ET_py._namespace_map
        except ImportError:
            warnings.warn("Couldn't import xml.etree.ElementTree; "
                    "phyloXML namespaces may have unexpected abbreviations "
                    "in the output.", ImportWarning, stacklevel=2)
            ElementTree._namespace_map = {}

    def register_namespace(prefix, uri):
        ElementTree._namespace_map[uri] = prefix

for prefix, uri in NAMESPACES.iteritems():
    register_namespace(prefix, uri)


class PhyloXMLError(Exception):
    """Exception raised when PhyloXML object construction cannot continue.

    XML syntax errors will be found and raised by the underlying ElementTree
    module; this exception is for valid XML that breaks the phyloXML
    specification.
    """
    pass


# ---------------------------------------------------------
# Public API

def read(file):
    """Parse a phyloXML file or stream and build a tree of Biopython objects.

    The children of the root node are phylogenies and possibly other arbitrary
    (non-phyloXML) objects.

    @rtype: Bio.Tree.PhyloXML.Phyloxml
    """
    return Parser(file).read()


def parse(file):
    """Iterate over the phylogenetic trees in a phyloXML file.

    This ignores any additional data stored at the top level, but may be more
    memory-efficient than the read() function.

    @return: a generator of Bio.Tree.PhyloXML.Phylogeny objects.
    """
    return Parser(file).parse()


def write(obj, file, encoding=None):
    """Write a phyloXML file.

    The first argument is an instance of Phyloxml, Phylogeny or BaseTree.Tree,
    or an iterable of either of the latter two. The object will be converted to
    a Phyloxml object before serialization.

    The file argument can be either an open handle or a file name.
    """
    if isinstance(obj, Tree.Phyloxml):
        pass
    elif isinstance(obj, Tree.Phylogeny):
        obj = obj.to_phyloxml()
    elif isinstance(obj, Tree.BaseTree.Tree):
        obj = Tree.Phylogeny.from_tree(obj).to_phyloxml()
    elif hasattr(obj, '__iter__'):
        obj = Tree.Phyloxml({}, phylogenies=obj)
    else:
        raise ValueError("First argument must be a Phyloxml, Phylogeny, "
                "Tree, or iterable of Trees or Phylogenies.")
    Writer(obj, encoding).write(file)


# ---------------------------------------------------------
# Functions I wish ElementTree had

def local(tag):
    """Extract the local tag from a namespaced tag name."""
    if tag[0] == '{':
        return tag[tag.index('}')+1:]
    return tag

def split_namespace(tag):
    """Split a tag into namespace and local tag strings."""
    try:
        return tag[1:].split('}', 1)
    except:
        return ('', tag)


def _ns(tag, namespace=NAMESPACES['phy']):
    """Format an XML tag with the given namespace."""
    return '{%s}%s' % (namespace, tag)

def get_child_as(parent, tag, construct):
    """Find a child node by tag, and pass it through a constructor.

    Returns None if no matching child is found.
    """
    child = parent.find(_ns(tag))
    if child is not None:
        return construct(child)

def get_child_text(parent, tag, construct=unicode):
    """Find a child node by tag; pass its text through a constructor.

    Returns None if no matching child is found.
    """
    child = parent.find(_ns(tag))
    if child is not None:
        return child.text and construct(child.text) or None

def get_children_as(parent, tag, construct):
    """Find child nodes by tag; pass each through a constructor.

    Returns an empty list if no matching child is found.
    """
    return [construct(child) for child in 
            parent.findall(_ns(tag))]

def get_children_text(parent, tag, construct=unicode):
    """Find child nodes by tag; pass each node's text through a constructor.

    Returns an empty list if no matching child is found.
    """
    return [construct(child.text) for child in 
            parent.findall(_ns(tag))
            if child.text]


def dump_tags(handle, file=sys.stdout):
    """Extract tags from an XML document, writing them to stdout by default.

    This utility is meant for testing and debugging.
    """
    for event, elem in ElementTree.iterparse(handle, events=('start', 'end')):
        if event == 'start':
            file.write(elem.tag + '\n')
        else:
            elem.clear()


# ---------------------------------------------------------
# INPUT
# ---------------------------------------------------------

def str2bool(text):
    if text == 'true':
        return True
    if text == 'false':
        return False
    raise ValueError('String could not be converted to boolean: ' + text)

def dict_str2bool(dct, keys):
    out = dct.copy()
    for key in keys:
        if key in out:
            out[key] = str2bool(out[key])
    return out

def _int(text):
    if text is not None:
        try:
            return int(text)
        except Exception:
            return None

def _float(text):
    if text is not None:
        try:
            return float(text)
        except Exception:
            return None

def collapse_wspace(text):
    """Replace all spans of whitespace with a single space character.

    Also remove leading and trailing whitespace. See "Collapse Whitespace
    Policy" in the U{ phyloXML spec glossary
    <http://phyloxml.org/documentation/version_100/phyloxml.xsd.html#Glossary>
    }.
    """
    if text is not None:
        return ' '.join(text.split())

def replace_wspace(text):
    """Replace tab, LF and CR characters with spaces, but don't collapse.

    See "Replace Whitespace Policy" in the U{ phyloXML spec glossary
    <http://phyloxml.org/documentation/version_100/phyloxml.xsd.html#Glossary>
    }.
    """
    for char in ('\t', '\n', '\r'):
        if char in text:
            text = text.replace(char, ' ')
    return text


class Parser(object):
    """Methods for parsing all phyloXML nodes from an XML stream.

    To minimize memory use, the tree of ElementTree parsing events is cleared
    after completing each phylogeny, clade, and top-level 'other' element.
    Elements below the clade level are kept in memory until parsing of the
    current clade is finished -- this shouldn't be a problem because clade is
    the only recursive element, and non-clade nodes below this level are of
    bounded size.
    """

    def __init__(self, file):
        # Get an iterable context for XML parsing events
        context = iter(ElementTree.iterparse(file, events=('start', 'end')))
        event, root = context.next()
        self.root = root
        self.context = context

    def read(self):
        """Parse the phyloXML file and create a single Phyloxml object."""
        phyloxml = Tree.Phyloxml(dict((local(key), val)
                                for key, val in self.root.items()))
        other_depth = 0
        for event, elem in self.context:
            namespace, localtag = split_namespace(elem.tag)
            if event == 'start':
                if namespace != NAMESPACES['phy']:
                    other_depth += 1
                    continue
                if localtag == 'phylogeny':
                    phylogeny = self._parse_phylogeny(elem)
                    phyloxml.phylogenies.append(phylogeny)
            if event == 'end' and namespace != NAMESPACES['phy']:
                # Deal with items not specified by phyloXML
                other_depth -= 1
                if other_depth == 0:
                    # We're directly under the root node -- evaluate
                    otr = self.other(elem, namespace, localtag)
                    phyloxml.other.append(otr)
                    self.root.clear()
        return phyloxml

    def parse(self):
        """Parse the phyloXML file incrementally and return each phylogeny."""
        phytag = _ns('phylogeny')
        for event, elem in self.context:
            if event == 'start' and elem.tag == phytag:
                yield self._parse_phylogeny(elem)

    # Special parsing cases -- incremental, using self.context

    def _parse_phylogeny(self, parent):
        """Parse a single phylogeny within the phyloXML tree.

        Recursively builds a phylogenetic tree with help from parse_clade, then
        clears the XML event history for the phylogeny element and returns
        control to the top-level parsing function.
        """
        phylogeny = Tree.Phylogeny(**dict_str2bool(parent.attrib,
                                                   ['rooted', 'rerootable']))
        list_types = {
                # XML tag, plural attribute
                'confidence':   'confidences',
                'property':     'properties',
                'clade_relation': 'clade_relations',
                'sequence_relation': 'sequence_relations',
                }
        for event, elem in self.context:
            namespace, tag = split_namespace(elem.tag)
            if event == 'start' and tag == 'clade':
                assert phylogeny.clade is None, \
                        "Phylogeny object should only have 1 clade"
                phylogeny.clade = self._parse_clade(elem)
                continue
            if event == 'end':
                if tag == 'phylogeny':
                    parent.clear()
                    break
                # Handle the other non-recursive children
                if tag in list_types:
                    getattr(phylogeny, list_types[tag]).append(
                            getattr(self, tag)(elem))
                # Complex types
                elif tag in ('date', 'id'):
                    setattr(phylogeny, tag, getattr(self, tag)(elem))
                # Simple types
                elif tag in ('name', 'description'):
                    setattr(phylogeny, tag, collapse_wspace(elem.text))
                # Unknown tags
                elif namespace != NAMESPACES['phy']:
                    phylogeny.other.append(self.other(elem, namespace, tag))
                    parent.clear()
                else:
                    # NB: This shouldn't happen in valid files
                    raise PhyloXMLError('Misidentified tag: ' + tag)
        return phylogeny

    _clade_complex_types = ['color', 'events', 'binary_characters', 'date']
    _clade_list_types = {
            'confidence':   'confidences',
            'distribution': 'distributions',
            'reference':    'references',
            'property':     'properties',
            }
    _clade_tracked_tags = set(_clade_complex_types + _clade_list_types.keys()
                              + ['branch_length', 'name', 'node_id', 'width'])

    def _parse_clade(self, parent):
        """Parse a Clade node and its children, recursively."""
        clade = Tree.Clade(**parent.attrib)
        if clade.branch_length is not None:
            clade.branch_length = float(clade.branch_length)
        # NB: Only evaluate nodes at the current level
        tag_stack = []
        for event, elem in self.context:
            namespace, tag = split_namespace(elem.tag)
            if event == 'start':
                if tag == 'clade':
                    clade.clades.append(self._parse_clade(elem))
                    continue
                if tag == 'taxonomy':
                    clade.taxonomies.append(self._parse_taxonomy(elem))
                    continue
                if tag == 'sequence':
                    clade.sequences.append(self._parse_sequence(elem))
                    continue
                if tag in self._clade_tracked_tags:
                    tag_stack.append(tag)
            if event == 'end':
                if tag == 'clade':
                    elem.clear()
                    break
                if tag != tag_stack[-1]:
                    continue
                tag_stack.pop()
                # Handle the other non-recursive children
                if tag in self._clade_list_types:
                    getattr(clade, self._clade_list_types[tag]).append(
                            getattr(self, tag)(elem))
                elif tag in self._clade_complex_types:
                    setattr(clade, tag, getattr(self, tag)(elem))
                elif tag == 'branch_length':
                    # NB: possible collision with the attribute
                    if clade.branch_length is not None:
                        raise PhyloXMLError(
                                'Attribute branch_length was already set '
                                'for this Clade.')
                    clade.branch_length = _float(elem.text)
                elif tag == 'width':
                    clade.width = _float(elem.text)
                elif tag == 'name':
                    clade.name = collapse_wspace(elem.text)
                elif tag == 'node_id':
                    clade.node_id = elem.text and elem.text.strip() or None
                elif namespace != NAMESPACES['phy']:
                    clade.other.append(self.other(elem, namespace, tag))
                    elem.clear()
                else:
                    raise PhyloXMLError('Misidentified tag: ' + tag)
        return clade

    def _parse_sequence(self, parent):
        sequence = Tree.Sequence(**parent.attrib)
        for event, elem in self.context:
            namespace, tag = split_namespace(elem.tag)
            if event == 'end':
                if tag == 'sequence':
                    parent.clear()
                    break
                if tag in ('accession', 'mol_seq', 'uri',
                        'domain_architecture'):
                    setattr(sequence, tag, getattr(self, tag)(elem))
                elif tag == 'annotation':
                    sequence.annotations.append(self.annotation(elem))
                elif tag == 'name': 
                    sequence.name = collapse_wspace(elem.text)
                elif tag in ('symbol', 'location'):
                    setattr(sequence, tag, elem.text)
                elif namespace != NAMESPACES['phy']:
                    sequence.other.append(self.other(elem, namespace, tag))
                    parent.clear()
        return sequence

    def _parse_taxonomy(self, parent):
        taxonomy = Tree.Taxonomy(**parent.attrib)
        for event, elem in self.context:
            namespace, tag = split_namespace(elem.tag)
            if event == 'end':
                if tag == 'taxonomy':
                    parent.clear()
                    break
                if tag in ('id', 'uri'):
                    setattr(taxonomy, tag, getattr(self, tag)(elem))
                elif tag == 'common_name':
                    taxonomy.common_names.append(collapse_wspace(elem.text))
                elif tag == 'synonym':
                    taxonomy.synonyms.append(elem.text)
                elif tag in ('code', 'scientific_name', 'authority', 'rank'):
                    # ENH: check_str on rank
                    setattr(taxonomy, tag, elem.text)
                elif namespace != NAMESPACES['phy']:
                    taxonomy.other.append(self.other(elem, namespace, tag))
                    parent.clear()
        return taxonomy

    def other(self, elem, namespace, localtag):
        return Tree.Other(localtag, namespace, elem.attrib,
                  value=elem.text and elem.text.strip() or None,
                  children=[self.other(child, *split_namespace(child.tag))
                            for child in elem])

    # Complex types

    def accession(self, elem):
        return Tree.Accession(elem.text.strip(), elem.get('source'))

    def annotation(self, elem):
        return Tree.Annotation(
                desc=collapse_wspace(get_child_text(elem, 'desc')),
                confidence=get_child_as(elem, 'confidence', self.confidence),
                properties=get_children_as(elem, 'property', self.property),
                uri=get_child_as(elem, 'uri', self.uri),
                **elem.attrib)

    def binary_characters(self, elem):
        def bc_getter(elem):
            return get_children_text(elem, 'bc')
        return Tree.BinaryCharacters(
                type=elem.get('type'),
                gained_count=_int(elem.get('gained_count')),
                lost_count=_int(elem.get('lost_count')),
                present_count=_int(elem.get('present_count')),
                absent_count=_int(elem.get('absent_count')),
                # Flatten BinaryCharacterList sub-nodes into lists of strings
                gained=get_child_as(elem, 'gained', bc_getter),
                lost=get_child_as(elem, 'lost', bc_getter),
                present=get_child_as(elem, 'present', bc_getter),
                absent=get_child_as(elem, 'absent', bc_getter))

    def clade_relation(self, elem):
        return Tree.CladeRelation(
                elem.get('type'), elem.get('id_ref_0'), elem.get('id_ref_1'),
                distance=elem.get('distance'),
                confidence=get_child_as(elem, 'confidence', self.confidence))

    def color(self, elem):
        red, green, blue = (get_child_text(elem, color, int) for color in
                            ('red', 'green', 'blue'))
        return Tree.BranchColor(red, green, blue)

    def confidence(self, elem):
        return Tree.Confidence(
                _float(elem.text),
                elem.get('type'))

    def date(self, elem):
        return Tree.Date(
                unit=elem.get('unit'),
                desc=collapse_wspace(get_child_text(elem, 'desc')),
                value=get_child_text(elem, 'value', float),
                minimum=get_child_text(elem, 'minimum', float),
                maximum=get_child_text(elem, 'maximum', float),
                )

    def distribution(self, elem):
        return Tree.Distribution(
                desc=collapse_wspace(get_child_text(elem, 'desc')),
                points=get_children_as(elem, 'point', self.point),
                polygons=get_children_as(elem, 'polygon', self.polygon))

    def domain(self, elem):
        return Tree.ProteinDomain(elem.text.strip(),
                int(elem.get('from')) - 1,
                int(elem.get('to')),
                confidence=_float(elem.get('confidence')),
                id=elem.get('id'))

    def domain_architecture(self, elem):
        return Tree.DomainArchitecture(
                length=int(elem.get('length')),
                domains=get_children_as(elem, 'domain', self.domain))

    def events(self, elem):
        return Tree.Events(
                type=get_child_text(elem, 'type'),
                duplications=get_child_text(elem, 'duplications', int),
                speciations=get_child_text(elem, 'speciations', int),
                losses=get_child_text(elem, 'losses', int),
                confidence=get_child_as(elem, 'confidence', self.confidence))

    def id(self, elem):
        provider = elem.get('provider') or elem.get('type')
        return Tree.Id(elem.text.strip(), provider)

    def mol_seq(self, elem):
        is_aligned = elem.get('is_aligned')
        if is_aligned is not None:
            is_aligned = str2bool(is_aligned)
        return Tree.MolSeq(elem.text.strip(), is_aligned=is_aligned)

    def point(self, elem):
        return Tree.Point(
                elem.get('geodetic_datum'),
                get_child_text(elem, 'lat', float),
                get_child_text(elem, 'long', float),
                alt=get_child_text(elem, 'alt', float),
                alt_unit=elem.get('alt_unit'))

    def polygon(self, elem):
        return Tree.Polygon(
                points=get_children_as(elem, 'point', self.point))

    def property(self, elem):
        return Tree.Property(elem.text.strip(),
                elem.get('ref'), elem.get('applies_to'), elem.get('datatype'),
                unit=elem.get('unit'),
                id_ref=elem.get('id_ref'))

    def reference(self, elem):
        return Tree.Reference(
                doi=elem.get('doi'),
                desc=get_child_text(elem, 'desc'))

    def sequence_relation(self, elem):
        return Tree.SequenceRelation(
                elem.get('type'), elem.get('id_ref_0'), elem.get('id_ref_1'),
                distance=_float(elem.get('distance')),
                confidence=get_child_as(elem, 'confidence', self.confidence))

    def uri(self, elem):
        return Tree.Uri(elem.text.strip(),
                desc=collapse_wspace(elem.get('desc')),
                type=elem.get('type'))



# ---------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------

def serialize(value):
    """Convert a Python primitive to a phyloXML-compatible Unicode string."""
    if isinstance(value, float):
        return unicode(value).upper()
    elif isinstance(value, bool):
        return unicode(value).lower()
    return unicode(value)


def _clean_attrib(obj, attrs):
    """Create a dictionary from an object's specified, non-None attributes."""
    out = {}
    for key in attrs:
        val = getattr(obj, key)
        if val is not None:
            out[key] = serialize(val)
    return out


def _handle_complex(tag, attribs, subnodes, has_text=False):
    def wrapped(self, obj):
        elem = ElementTree.Element(tag, _clean_attrib(obj, attribs))
        for subn in subnodes:
            if isinstance(subn, basestring):
                # singular object: method and attribute names are the same
                if getattr(obj, subn) is not None:
                    elem.append(getattr(self, subn)(getattr(obj, subn)))
            else:
                # list: singular method, pluralized attribute name
                method, plural = subn
                for item in getattr(obj, plural):
                    elem.append(getattr(self, method)(item))
        if has_text:
            elem.text = serialize(obj.value)
        return elem
    wrapped.__doc__ = "Serialize a %s and its subnodes, in order." % tag
    return wrapped


def _handle_simple(tag):
    def wrapped(self, obj):
        elem = ElementTree.Element(tag)
        elem.text = serialize(obj)
        return elem
    wrapped.__doc__ = "Serialize a simple %s node." % tag
    return wrapped


class Writer(object):
    """Methods for serializing a phyloXML object to XML.
    """
    def __init__(self, phyloxml, encoding):
        """Build an ElementTree from a phyloXML object."""
        assert isinstance(phyloxml, Tree.Phyloxml), "Not a Phyloxml object"
        self._tree = ElementTree.ElementTree(self.phyloxml(phyloxml))
        self.encoding = encoding

    def write(self, file):
        if self.encoding is not None:
            self._tree.write(file, self.encoding)
        else:
            self._tree.write(file)

    # Convert classes to ETree elements

    def phyloxml(self, obj):
        elem = ElementTree.Element(_ns('phyloxml'),
                # NB: This is for XSD validation, which we don't do
                # {_ns('schemaLocation', NAMESPACES['xsi']):
                #     obj.attributes['schemaLocation'],
                #     }
                )
        for tree in obj.phylogenies:
            elem.append(self.phylogeny(tree))
        for otr in obj.other:
            elem.append(self.other(otr))
        return elem

    def other(self, obj):
        elem = ElementTree.Element(_ns(obj.tag, obj.namespace), obj.attributes)
        elem.text = obj.value
        for child in obj.children:
            elem.append(self.other(child))
        return elem

    phylogeny = _handle_complex(_ns('phylogeny'),
            ('rooted', 'rerootable', 'branch_length_unit', 'type'),
            ( 'name',
              'id',
              'description',
              'date',
              ('confidence',        'confidences'),
              'clade',
              ('clade_relation',    'clade_relations'),
              ('sequence_relation', 'sequence_relations'),
              ('property',          'properties'),
              ('other',             'other'),
              ))

    clade = _handle_complex(_ns('clade'), ('id_source',),
            ( 'name',
              'branch_length',
              ('confidence',    'confidences'),
              'width',
              'color',
              'node_id',
              ('taxonomy',      'taxonomies'),
              ('sequence',      'sequences'),
              'events',
              'binary_characters',
              ('distribution',  'distributions'),
              'date',
              ('reference',     'references'),
              ('property',      'properties'),
              ('clade',         'clades'),
              ('other',         'other'),
              ))

    accession = _handle_complex(_ns('accession'), ('source',),
            (), has_text=True)

    annotation = _handle_complex(_ns('annotation'),
            ('ref', 'source', 'evidence', 'type'),
            ( 'desc',
              'confidence',
              ('property',   'properties'),
              'uri',
              ))

    def binary_characters(self, obj):
        """Serialize a binary_characters node and its subnodes."""
        elem = ElementTree.Element(_ns('binary_characters'),
                _clean_attrib(obj,
                    ('type', 'gained_count', 'lost_count',
                        'present_count', 'absent_count')))
        for subn in ('gained', 'lost', 'present', 'absent'):
            subelem = ElementTree.Element(_ns(subn))
            for token in getattr(obj, subn):
                subelem.append(self.bc(token))
            elem.append(subelem)
        return elem

    clade_relation = _handle_complex(_ns('clade_relation'),
            ('id_ref_0', 'id_ref_1', 'distance', 'type'),
            ('confidence',))

    color = _handle_complex(_ns('color'), (), ('red', 'green', 'blue'))

    confidence = _handle_complex(_ns('confidence'), ('type',),
            (), has_text=True)

    date = _handle_complex(_ns('date'), ('unit',),
            ('desc', 'value', 'minimum', 'maximum'))

    distribution = _handle_complex(_ns('distribution'), (),
            ( 'desc',
              ('point',     'points'),
              ('polygon',   'polygons'),
              ))

    def domain(self, obj):
        """Serialize a domain node."""
        elem = ElementTree.Element(_ns('domain'),
                {'from': str(obj.start + 1), 'to': str(obj.end)})
        if obj.confidence is not None:
            elem.set('confidence', serialize(obj.confidence))
        if obj.id is not None:
            elem.set('id', obj.id)
        elem.text = serialize(obj.value)
        return elem

    domain_architecture = _handle_complex(_ns('domain_architecture'),
            ('length',),
            (('domain', 'domains'),))

    events = _handle_complex(_ns('events'), (),
            ( 'type',
              'duplications',
              'speciations',
              'losses',
              'confidence',
              ))

    id = _handle_complex(_ns('id'), ('provider',), (), has_text=True)

    mol_seq = _handle_complex(_ns('mol_seq'), ('is_aligned',),
            (), has_text=True)

    node_id = _handle_complex(_ns('node_id'), ('provider',), (), has_text=True)

    point = _handle_complex(_ns('point'), ('geodetic_datum', 'alt_unit'),
            ('lat', 'long', 'alt'))

    polygon = _handle_complex(_ns('polygon'), (), (('point', 'points'),))

    property = _handle_complex(_ns('property'),
            ('ref', 'unit', 'datatype', 'applies_to', 'id_ref'),
            (), has_text=True)

    reference = _handle_complex(_ns('reference'), ('doi',), ('desc',))

    sequence = _handle_complex(_ns('sequence'),
            ('type', 'id_ref', 'id_source'),
            ( 'symbol',
              'accession',
              'name',
              'location',
              'mol_seq',
              'uri',
              ('annotation', 'annotations'),
              'domain_architecture',
              ('other', 'other'),
              ))

    sequence_relation = _handle_complex(_ns('sequence_relation'),
            ('id_ref_0', 'id_ref_1', 'distance', 'type'),
            ('confidence',))

    taxonomy = _handle_complex(_ns('taxonomy'),
            ('id_source',),
            ( 'id',
              'code',
              'scientific_name',
              'authority',
              ('common_name',   'common_names'),
              ('synonym',   'synonyms'),
              'rank',
              'uri',
              ('other',         'other'),
              ))

    uri = _handle_complex(_ns('uri'), ('desc', 'type'), (), has_text=True)

    # Primitive types

    # Floating point
    alt = _handle_simple(_ns('alt'))
    branch_length = _handle_simple(_ns('branch_length'))
    lat = _handle_simple(_ns('lat'))
    long = _handle_simple(_ns('long'))
    value = _handle_simple(_ns('value'))
    width = _handle_simple(_ns('width'))

    # Integers
    blue = _handle_simple(_ns('blue'))
    duplications = _handle_simple(_ns('duplications'))
    green = _handle_simple(_ns('green'))
    losses = _handle_simple(_ns('losses'))
    red = _handle_simple(_ns('red'))
    speciations = _handle_simple(_ns('speciations'))

    # Strings
    bc = _handle_simple(_ns('bc'))
    code = _handle_simple(_ns('code'))      # TaxonomyCode
    common_name = _handle_simple(_ns('common_name'))
    desc = _handle_simple(_ns('desc'))
    description = _handle_simple(_ns('description'))
    location = _handle_simple(_ns('location'))
    mol_seq = _handle_simple(_ns('mol_seq'))
    name = _handle_simple(_ns('name'))
    rank = _handle_simple(_ns('rank')) # Rank
    scientific_name = _handle_simple(_ns('scientific_name'))
    symbol = _handle_simple(_ns('symbol'))
    synonym = _handle_simple(_ns('synonym'))
    type = _handle_simple(_ns('type')) # EventType
