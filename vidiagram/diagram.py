import os
import unittest

from pylabview_helpers import vi
from pprint import pprint
import graphviz

this_dir = os.path.dirname(os.path.realpath(__file__))

uuid_dict = {}

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
    if class_type == LVheap.SL_CLASS_TAGS.SL__label:
        return Label(node)

    else:
        # raise node
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
        self._uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]

    def __str__(self):
        return "WeakNode" + str(self._uuid)

    __repr__ = __str__

class Signal:
    def __init__(self, terminal_list):
        self._terminals = []
        for terminal in iterate_direct_children(terminal_list):
            uuid = terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
            self._terminals.append(uuid)
            node_to_object_and_uuid_dict(terminal) # in case any actual objects show up here instead of just references, resolve them, not sure if this is possible

    def fill_graph(self, graph, namespace):
        if not self._terminals or len(self._terminals) == 1:
            return
        iterator = iter(self._terminals)
        source = next(iterator)
        for dest in iterator:
            graph.edge(uuid_dict[source].name, uuid_dict[dest].name)


class Node:
    def __init__(self, node):
        self._node = node
        self._uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        self._terminals = []
        self._resolved_weaknodes = False
        self._color = None
        self._style = None

        terminal_list = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
        for terminal in iterate_direct_children(terminal_list):
            # print("Parsing termlist: " + str(terminal))
            self._terminals.append(node_to_object_and_uuid_dict(terminal))
        bounds = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__bounds)

        if bounds:
            self.x = (bounds.right + bounds.left) / 2
            self.y = (bounds.top + bounds.bottom) / 2

    def resolve_weak_nodes(self):
        if self._resolved_weaknodes:
            return
        print("resolve: " + str(self))
        for index, terminal in enumerate(self._terminals):
            if isinstance(terminal, WeakNode):
                print("resolving: " + str(terminal))
                self._terminals[index] = node_to_object_and_uuid_dict(terminal._node)
        for terminal in self._terminals:
            terminal.resolve_weak_nodes()
            terminal.set_parent(self)
        self._resolved_weaknodes = True

    @property
    def name(self):
        if len(self._terminals) > 0:
            return "cluster" + str(self._uuid)
        return str(self._uuid)

    @property
    def label(self):
        return type(self).__name__

    def fill_graph(self, graph, namespace):
        struct_info = ""
        # if no or 1 terminal, maybe just make it a node
        if len(self._terminals) > 0:
            with graph.subgraph(name=self.name) as subgraph:
                subgraph.attr(label=self.label, color=self._color, style="filled")
                for terminal in self._terminals:
                # name = f"<{str(terminal._uuid)}> Terminal"
                # struct_info += name + " | "
                    print(terminal)
                    terminal.fill_graph(subgraph, namespace)
        else:
            graph.node(name=self.name, label=self.label, color=self._color, style=self._style)


class UnknownNode(Node):
    def __init__(self, node):
        super().__init__(node)
        print(f"Unknown {get_class_type(node)}")

    def __str__(self):
        return "UnknownNode"

    def set_parent(self, parent):
        self._parent = parent

    __repr__ = __str__


class Label(Node):
    def __init__(self, node):
        super().__init__(node)
        textrec = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__textRec)
        print(textrec)
        text = textrec.findChild(LVheap.OBJ_TEXT_HAIR_TAGS.OF__text)
        self._label = text.content.decode("cp1252")
        self._color = "lightyellow"
        self._style = "filled"

    @property
    def label(self):
        return self._label

class FPTerminal(Node):
    def __init__(self, node):
        super().__init__(node)

    def __str__(self):
        return "FPTerminal"

    def set_parent(self, parent):
        self._parent = parent

    __repr__ = __str__

class Terminal(Node):
    def __init__(self, node):
        super().__init__(node)
        subclass = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__dco)
        # print("Terminal: "+str(self._uuid))
        self._impl = node_to_object_and_uuid_dict(subclass)
        self._parent = None

    def resolve_weak_nodes(self):
        if self._resolved_weaknodes:
            return
        # print("resolve terminals")
        super().resolve_weak_nodes()
        if isinstance(self._impl, WeakNode):
            self._impl = node_to_object_and_uuid_dict(self._impl._node)
        self._impl.resolve_weak_nodes() # TODO why does this recurse forever
        self._impl.set_parent(self)

    def set_parent(self, parent):
        # if self._parent and self._parent is not parent:
            # print(f"parent: {parent} self._parent {self._parent}")
            # raise "Wtf"
        self._parent = parent

    def fill_graph(self, graph, namespace):
        # graph.node(name=self.name, label=type(self._impl).__name__)
        print(self._impl)
        self._impl.fill_graph(graph, namespace)

    @property
    def is_input(self):
        return not isinstance(terminal._impl, Output)

    @property
    def name(self):
        return str(self._uuid)

    def __str__(self):
        return "Terminal"

    __repr__ = __str__

class LoopTunnel(Node):
    def __init__(self, node):
        super().__init__(node)

    def set_parent(self, parent):
        self._parent = parent
        # for some reason, looptunnels are owned by a terminal, they own
            # <SL__arrayElement class="term" uid="307">
            # <objFlags>2129984</objFlags>
            # <dco class="lpTun" uid="304">
              # <objFlags>2048</objFlags>
              # <termList elements="2">
                # <SL__arrayElement uid="306" />
                # <SL__arrayElement uid="307" />
                # </termList>
              # </dco>
            # </SL__arrayElement>
        # look at 306, so to prevent recursion problems, ignore our parent
        # self._terminals.remove(parent)
        print(self._terminals)

    def fill_graph(self, graph, namespace):
        struct_info = ""
        # if no or 1 terminal, maybe just make it a node
        if len(self._terminals) > 0:
            with graph.subgraph(name=self.name) as subgraph:
                subgraph.attr(label=type(self).__name__)
                for terminal in self._terminals:
                # name = f"<{str(terminal._uuid)}> Terminal"
                # struct_info += name + " | "
                    print(terminal)
                    subgraph.node(name=terminal.name, label=type(terminal).__name__)
        else:
            graph.node(name=self.name, label=type(self).__name__)


class TerminalClass(Node):
    def __init__(self, node):
        super().__init__(node)

    def fill_graph(self, graph, namespace):
        graph.node(name=self._parent.name, label=type(self).__name__)

    def set_parent(self, parent):
        self._parent = parent

class Constant(TerminalClass):
    def __init__(self, node):
        super().__init__(node)

class Parameter(TerminalClass):
    def __init__(self, node):
        super().__init__(node)

class Output(TerminalClass):
    def __init__(self, node):
        super().__init__(node)

class Primitive(Node):
    def __init__(self, node):
        super().__init__(node)
        self._primitive_id = node.attribs[LVheap.SL_SYSTEM_TAGS.SL__object.value]
        self._color = "lightyellow"

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
            for terminal in self._terminals:
                terminal.fill_graph(subgraph, namespace)

    def resolve_weak_nodes(self):
        if self._resolved_weaknodes:
            return
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
        self._signals = []

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
            self._signals.append(Signal(connected_terminals))

    def resolve_weak_nodes(self):
        super().resolve_weak_nodes()
        for index, node in enumerate(self._nodes):
            if isinstance(node, WeakNode):
                self._nodes[index] = node_to_object_and_uuid_dict(node._node)
        for node in self._nodes:
            node.resolve_weak_nodes()

    def fill_graph(self, graph, namespace=""):
        for signal in self._signals:
            signal.fill_graph(graph, namespace)
        with graph.subgraph(name="cluster" + str(self._uuid), node_attr={"shape": "record"}) as subgraph:
            subgraph.attr(label=type(self).__name__)
            for node in self._nodes:
                node.fill_graph(subgraph, namespace)
            # for terminal in self._terminals:
                # terminal.fill_graph(subgraph, namespace)

    def __str__(self):
        return "Diagram:" + str(self._nodes)

    __repr__ = __str__



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
                    g = graphviz.Digraph('G', engine='dot', node_attr={"shape": "record"})
                    diagram.fill_graph(g)
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
                pprint(uuid_dict)
                g = graphviz.Digraph('G', engine='dot', format="svg", node_attr={"shape": "record"})
                diagram.fill_graph(g)
                print(g.source)
                return g

import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", action="store")
    options = parser.parse_args()
    graph = get_dot_graph(options.file)
    graph.view()

if __name__ == "__main__":
    main()
