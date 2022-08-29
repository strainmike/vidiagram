import os
import unittest

from pylabview_helpers import vi
from pprint import pprint
import graphviz

this_dir = os.path.dirname(os.path.realpath(__file__))

uuid_dict = {}
signals = {}
signals_to_draw = {}

from pylabview import LVheap
def get_class_type(node):
    if LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value in node.attribs:
        return node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value]
    return None

def node_to_object(node):
    class_type = get_class_type(node)
    subclass = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__dco)
    if subclass:
        subclass_node = node_to_object_and_uuid_dict(subclass)
        subclass_type = get_class_type(subclass)

    # print(class_type)
    # print(subclass)
    if class_type is None and LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
        return WeakNode(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__diag:
        return Diagram(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__whileLoop:
        return WhileLoop(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__forLoop:
        return WhileLoop(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__prim:
        return Primitive(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__bDConstDCO:
        return Constant(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__fPTerm:
        return FPTerminal(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__term:
        # if subclass:
            # if subclass_type == LVheap.SL_CLASS_TAGS.SL__parm:
            # if subclass_type == LVheap.SL_CLASS_TAGS.SL__overridableParm:
            # if subclass_type == LVheap.SL_CLASS_TAGS.SL__lpTun:
        return Terminal(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lpTun:
        return LoopTunnel(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__parm:
        return Parameter(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__overridableParm:
        return Output(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__bDConstDCO:
        return Constant(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lTst:
        return LoopTest(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lCnt:
        return LoopCount(node)

    else:
        raise node
        return UnknownNode(node)

def node_to_object_and_uuid_dict(node):
    if node.getScopeInfo() is LVheap.NODE_SCOPE.TagClose:
        return
    if LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
        uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        # print(uuid)
        if uuid in uuid_dict:
            return uuid_dict[uuid]
    graph_node = node_to_object(node)
    if not isinstance(graph_node, WeakNode) and LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
        uuid_dict[uuid] = graph_node
    return graph_node


class WeakNode:
    # needs reinserted later to resolve the full node
    def __init__(self, node):
        self._node = node

    def __str__(self):
        return "WeakNode" + str(self._node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value])

    __repr__ = __str__


def add_signal(signal_map, source, dest):
    if source not in signal_map:
        signal_map[source] = set()
    signal_map[source].add(dest)

def get_source(uuid):
    for source, dests in signals.items():
        for dest in dests:
            if dest == uuid:
                uuid = source
                return get_source(uuid)
    return uuid


def get_dest(uuid):
    if uuid in signals and len(signals[uuid]) == 1:
        uuid = signals[uuid].pop()
        return get_dest(uuid)
    return uuid


class Node:
    def __init__(self, node):
        self._node = node
        self._uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        self._terminals = []

        terminal_list = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
        for terminal in iterate_direct_children(terminal_list):
            # print("Parsing termlist: " + str(terminal))
            self._terminals.append(node_to_object_and_uuid_dict(terminal))
        bounds = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__bounds)

        if bounds:
            self.x = (bounds.right + bounds.left) / 2
            self.y = (bounds.top + bounds.bottom) / 2

    def resolve_weak_nodes(self):
        # print("resolve: " + str(self))
        for index, terminal in enumerate(self._terminals):
            if isinstance(terminal, WeakNode):
                self._terminals[index] = node_to_object_and_uuid_dict(terminal._node)
        for terminal in self._terminals:
            terminal.resolve_weak_nodes()

    def fill_graph(self, graph, namespace):
        graph.node(name=str(self._uuid), label=type(self).__name__, pos=f"{int(self.x)},{int(self.y)}")
        self.fill_terminals(graph, namespace)

    def fill_terminals(self, graph, namespace):
        for terminal in self._terminals:
            # print(terminal._uuid)
            if isinstance(terminal, FPTerminal):
                terminal.fill_graph(graph, namespace)
            elif isinstance(terminal._impl, Constant) \
                or isinstance(terminal._impl, LoopCount) \
                or isinstance(terminal._impl, LoopTest):
                terminal.fill_graph(graph, namespace)
            elif isinstance(terminal._impl, Parameter):
                add_signal(signals, terminal._uuid, self._uuid)
                source = terminal._uuid
                dest = self._uuid
                source = get_source(source)
                add_signal(signals_to_draw, source, dest)
            elif isinstance(terminal._impl, Output):
                for dest in signals[terminal._uuid]:
                    add_signal(signals, self._uuid, dest)
                dest = terminal._uuid
                dest = get_dest(dest)
                source = self._uuid
                add_signal(signals_to_draw, source, dest)
            elif isinstance(terminal._impl, LoopTunnel):
                source = terminal._impl._source
                dest = terminal._impl._dest



class UnknownNode(Node):
    def __init__(self, node):
        super().__init__(node)

    def __str__(self):
        return "UnknownNode"

    __repr__ = __str__


class Constant(Node):
    def __init__(self, node):
        super().__init__(node)

    def __str__(self):
        return "Constant"

    __repr__ = __str__


class FPTerminal(Node):
    def __init__(self, node):
        super().__init__(node)

    def __str__(self):
        return "FPTerminal"

    __repr__ = __str__


# TODO, redo how we do signals
# Nodes should keep track of their own signals and resolve them themselves
# That enables fancier edge stuff

class Terminal(Node):
    def __init__(self, node):
        super().__init__(node)
        subclass = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__dco)
        # print("Terminal: "+str(self._uuid))
        self._impl = node_to_object_and_uuid_dict(subclass)

    def resolve_weak_nodes(self):
        # print("resolve terminals")
        super().resolve_weak_nodes()
        if isinstance(self._impl, WeakNode):
            self._impl = node_to_object_and_uuid_dict(self._impl._node)

    def fill_graph(self, graph, namespace):
        self._impl.fill_graph(graph, namespace, self)

    def __str__(self):
        return "Terminal"

    __repr__ = __str__

class LoopTunnel(Node):
    def __init__(self, node):
        super().__init__(node)
        connected_terminals = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
        # print(connected_terminals)
        iterator = iterate_direct_children(connected_terminals)
        source = next(iterator)
        source_uuid = source.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        for terminal in iterator:
            add_signal(signals, source_uuid, terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value])
            add_signal(signals, terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value], source_uuid)
        self._source = source_uuid
        self._dest = terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]

class Parameter(Node):
    def __init__(self, node):
        super().__init__(node)

class Output(Node):
    def __init__(self, node):
        super().__init__(node)


class TerminalClass(Node):
    def fill_graph(self, graph, namespace, parent):
        graph.node(name=str(parent._uuid), label=type(self).__name__)
        source = get_source(parent._uuid)
        dest = get_dest(parent._uuid)
        if source != dest:
            add_signal(signals_to_draw, source, dest)



class Constant(TerminalClass):
    def __init__(self, node):
        super().__init__(node)

class Primitive(Node):
    def __init__(self, node):
        super().__init__(node)
        self._primitive_id = node.attribs[LVheap.SL_SYSTEM_TAGS.SL__object.value]

    def __str__(self):
        return "Primitive ID: " + str(self._primitive_id)

    __repr__ = __str__

class Structure(Node):
    def __init__(self, node):
        super().__init__(node)
        diagram_list = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__diagramList)
        diagram_list_size = diagram_list.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__elements.value]
        self._diagrams = []
        for diagram_index in range(diagram_list_size):
            raw_diagram = diagram_list.findChild(LVheap.SL_SYSTEM_TAGS.SL__arrayElement, diagram_index)
            self._diagrams.append(node_to_object_and_uuid_dict(raw_diagram))

    def fill_graph(self, graph, namespace):
        with graph.subgraph(name="cluster" + str(self._uuid)) as subgraph:
            subgraph.attr(label=type(self).__name__)
            for diagram in self._diagrams:
                diagram.fill_graph(subgraph, namespace)
            self.fill_terminals(graph, namespace)
            # for terminal in self._terminals:
                # terminal.fill_graph(subgraph, namespace)

    def resolve_weak_nodes(self):
        super().resolve_weak_nodes()
        for diagram in self._diagrams:
            diagram.resolve_weak_nodes()

    def __str__(self):
        return type(self).__name__ + ":" + str(self._diagrams)

    __repr__ = __str__


class LoopTest(TerminalClass):
    def __init__(self, node):
        super().__init__(node)

class LoopCount(TerminalClass):
    def __init__(self, node):
        super().__init__(node)


class Loop(Structure):
    def __init__(self, node):
        super().__init__(node)
        self._loopIndex = node_to_object_and_uuid_dict(node.findChild(LVheap.OBJ_FIELD_TAGS.OF__loopIndexDCO))
        self._loopTest = node_to_object_and_uuid_dict(node.findChild(LVheap.OBJ_FIELD_TAGS.OF__loopTestDCO))



class WhileLoop(Loop): pass
class ForLoop(Loop): pass

def iterate_direct_children(node):
    if node is None:
        return
    current_level = 0
    for child in node.childs:
        if child.getScopeInfo() is not LVheap.NODE_SCOPE.TagClose:
            yield child

class Diagram(Node):
    def __init__(self, node):
        super().__init__(node)
        self._nodes = []
        self._terminals = []

        nodelist = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__nodeList)
        for nodelist_item in iterate_direct_children(nodelist):
            if get_class_type(nodelist_item) == LVheap.SL_CLASS_TAGS.SL__sRN:
                terminals = nodelist_item.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
                for terminal in iterate_direct_children(terminals):
                    subnode = node_to_object_and_uuid_dict(terminal)
                    if subnode:
                        self._terminals.append(subnode)

        zPlaneList = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__zPlaneList)
        for child_node in zPlaneList.childs:
            subnode = node_to_object_and_uuid_dict(child_node)
            if subnode:
                self._nodes.append(subnode)
        signallist = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__signalList)
        for signal in iterate_direct_children(signallist):
            connected_terminals = signal.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
            # print(connected_terminals)
            iterator = iterate_direct_children(connected_terminals)
            source = next(iterator)
            source_uuid = source.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
            for terminal in iterator:
                add_signal(signals, source_uuid, terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value])

    def resolve_weak_nodes(self):
        super().resolve_weak_nodes()
        for index, node in enumerate(self._nodes):
            if isinstance(node, WeakNode):
                self._nodes[index] = node_to_object_and_uuid_dict(node._node)
        for node in self._nodes:
            node.resolve_weak_nodes()

    def fill_graph(self, graph, namespace=""):
        with graph.subgraph(name="cluster" + str(self._uuid)) as subgraph:
            subgraph.attr(label=type(self).__name__)
            for node in self._nodes:
                node.fill_graph(subgraph, namespace)
            self.fill_terminals(graph, namespace)
            # for terminal in self._terminals:
                # terminal.fill_graph(subgraph, namespace)

    def __str__(self):
        return "Diagram:" + str(self._nodes)

    __repr__ = __str__

def add_wires(graph):
    for source, dests in signals_to_draw.items():
        for dest in dests:
            graph.edge(str(source), str(dest))


class TestDiagram(unittest.TestCase):
    def test_parse_diagram(self):
        vi_obj = vi.get_vi(os.path.join(this_dir, "add.vi"))
        for block in vi_obj.blocks.values():
            block_identifier = bytearray(block.header.ident).decode()
            if 'BDH' in block_identifier:
                # print(block.sections)
                for index, section in block.sections.items():
                    root = section.objects[0].childs[0]
                    diagram = node_to_object_and_uuid_dict(root)
                    diagram.resolve_weak_nodes()
                    # print(diagram)
                    # pprint(uuid_dict)
                    # pprint(signals)
                    g = graphviz.Digraph('G', engine='dot')
                    diagram.fill_graph(g)
                    add_wires(g)
                    # g.view()
                    # print(g.source)
            # breakpoint()

def get_dot_graph(file):
    vi_obj = vi.get_vi(file)
    for block in vi_obj.blocks.values():
        block_identifier = bytearray(block.header.ident).decode()
        if 'BDH' in block_identifier:
            # print(block.sections)
            for index, section in block.sections.items():
                root = section.objects[0].childs[0]
                diagram = node_to_object_and_uuid_dict(root)
                diagram.resolve_weak_nodes()
                print(diagram)
                # pprint(uuid_dict)
                # pprint(signals)
                g = graphviz.Digraph('G', engine='dot', format="svg")
                diagram.fill_graph(g)
                add_wires(g)
                return g
                # print(g.source)

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", action="store")
    options = parser.parse_args()
    graph = get_dot_graph(options.file)
    graph.view()

if __name__ == "__main__":
    main()
