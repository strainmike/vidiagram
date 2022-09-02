import os
import unittest

from pylabview_helpers import vi
from pprint import pprint
import graphviz

this_dir = os.path.dirname(os.path.realpath(__file__))

from pylabview import LVheap
def get_class_type(node):
    if LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value in node.attribs:
        return node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__class.value]
    return None

def _node_to_object(uuid_manager, node):
    class_type = get_class_type(node)
    # print(class_type)
    if class_type is None and LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
        return WeakNode(node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__diag:
        return Diagram(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__whileLoop:
        return WhileLoop(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__forLoop:
        return WhileLoop(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__select:
        return CaseStructure(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__prim:
        return Primitive(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__bDConstDCO:
        return Constant(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__fPTerm:
        return FPTerminal(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__term:
        return Terminal(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lpTun:
        return LoopTunnel(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__selTun:
        return SelectTunnel(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__caseSel:
        return CaseSelect(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__parm:
        return Parameter(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__overridableParm:
        return Output(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__bDConstDCO:
        return Constant(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lTst:
        return LoopTest(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__lCnt:
        return LoopCount(uuid_manager, node)
    if class_type == LVheap.SL_CLASS_TAGS.SL__label:
        return Label(uuid_manager, node)

    else:
        # raise node
        return UnknownNode(uuid_manager, node)

class UUIDManager:
    def __init__(self, uuids_to_nodes):
        self._uuids_to_nodes = uuids_to_nodes
        self._uuids_to_obj = {}
        for uuid, node in uuids_to_nodes.items():
            self._uuids_to_obj[uuid] = self.node_to_object(node)
        for uuid, node_obj in self._uuids_to_obj.items():
            node_obj.resolve_weak_nodes()

    def node_to_object(self, node):
        if node.getScopeInfo() is LVheap.NODE_SCOPE.TagClose:
            return
        if LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value not in node.attribs:
            raise RuntimeError("No UUID")
        uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        # print(uuid)
        if uuid in self._uuids_to_obj:
            return self._uuids_to_obj[uuid]
        graph_node = _node_to_object(self, self._uuids_to_nodes[uuid])
        if not isinstance(graph_node, WeakNode) and LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
            self._uuids_to_obj[uuid] = graph_node
        return graph_node

    def lookup_node_object(self, uuid):
        return self._uuids_to_obj[uuid]


class WeakNode:
    # needs reinserted later to resolve the full node
    # VIs can have circular references within nodes, so need
    # to lazy initialize
    def __init__(self, node):
        self._node = node
        self._uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]

    def __str__(self):
        return "WeakNode" + str(self._uuid)

    __repr__ = __str__

class Signal:
    def __init__(self, uuid_manager, terminal_list):
        self._terminals = []
        for terminal in iterate_direct_children(terminal_list):
            uuid = terminal.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
            self._terminals.append(uuid)
            self.uuid_manager = uuid_manager
            uuid_manager.node_to_object(terminal) # in case any actual objects show up here instead of just references, resolve them, not sure if this is possible

    def fill_graph(self, graph, namespace):
        if not self._terminals or len(self._terminals) == 1:
            return
        iterator = iter(self._terminals)
        source = next(iterator)
        for dest in iterator:
            graph.edge(self.uuid_manager.lookup_node_object(source).name, self.uuid_manager.lookup_node_object(dest).name)


class Node:
    def __init__(self, uuid_manager, node):
        self._node = node
        self._uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
        self._terminals = []
        self._color = None
        self._style = None
        self.uuid_manager = uuid_manager

        self._impl = None
        subclass = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__dco)
        if subclass:
            self._impl = WeakNode(subclass)

        terminal_list = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
        for terminal in iterate_direct_children(terminal_list):
            self._terminals.append(WeakNode(terminal))
        bounds = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__bounds)

        if bounds:
            self.x = (bounds.right + bounds.left) / 2
            self.y = (bounds.top + bounds.bottom) / 2

    def resolve_weak_nodes(self):
        for index, terminal in enumerate(self._terminals):
            if isinstance(terminal, WeakNode):
                self._terminals[index] = self.uuid_manager.node_to_object(terminal._node)
        for terminal in self._terminals:
            terminal.set_parent(self)
        if self._impl:
            if isinstance(self._impl, WeakNode):
                self._impl = self.uuid_manager.node_to_object(self._impl._node)
                self._impl.set_parent(self)

    @property
    def name(self):
        if len(self._terminals) > 0:
            return "cluster" + str(self._uuid)
        return str(self._uuid)

    @property
    def label(self):
        return type(self).__name__

    def fill_graph(self, graph, namespace):
        if len(self._terminals) > 0:
            with graph.subgraph(name=self.name) as subgraph:
                subgraph.attr(label=self.label, fillcolor=self._color, style="filled,solid")
                for terminal in self._terminals:
                    terminal.fill_graph(subgraph, namespace)
        else:
            graph.node(name=self.name, label=self.label, fillcolor=self._color, style=self._style)


class UnknownNode(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        print(f"Unknown {get_class_type(node)}")

    def __str__(self):
        return "UnknownNode"

    def set_parent(self, parent):
        self._parent = parent

    __repr__ = __str__


class Label(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        textrec = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__textRec)
        text = textrec.findChild(LVheap.OBJ_TEXT_HAIR_TAGS.OF__text)
        if text:
            self._label = text.content.decode("cp1252")
        self._color = "lightyellow"
        self._style = "filled,solid"

    @property
    def label(self):
        return self._label

class FPTerminal(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

    def __str__(self):
        return "FPTerminal"

    def set_parent(self, parent):
        self._parent = parent

    __repr__ = __str__

class Terminal(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        self._parent = None

    def set_parent(self, parent):
        # if self._parent and self._parent is not parent:
            # print(f"parent: {parent} self._parent {self._parent}")
            # raise "Wtf"
        self._parent = parent

    def fill_graph(self, graph, namespace):
        # graph.node(name=self.name, label=type(self._impl).__name__)
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

class Tunnel(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

    def set_parent(self, parent):
        self._parent = parent

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

class LoopTunnel(Tunnel): pass
class SelectTunnel(Tunnel): pass
class CaseSelect(Tunnel): pass

class TerminalClass(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

    def fill_graph(self, graph, namespace):
        graph.node(name=self._parent.name, label=type(self).__name__)

    def set_parent(self, parent):
        self._parent = parent

class Constant(TerminalClass):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

class Parameter(TerminalClass):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

class Output(TerminalClass):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

class Primitive(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        self._primitive_id = node.attribs[LVheap.SL_SYSTEM_TAGS.SL__object.value]
        self._color = "lightyellow"

    def __str__(self):
        return "Primitive ID: " + str(self._primitive_id)

    __repr__ = __str__

class Structure(Node):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        diagram_list = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__diagramList)
        self._diagrams = []
        for diagram in iterate_direct_children(diagram_list):
            self._diagrams.append(uuid_manager.node_to_object(diagram))

    def fill_graph(self, graph, namespace):
        with graph.subgraph(name="cluster" + str(self._uuid)) as subgraph:
            subgraph.attr(label=type(self).__name__)
            for diagram in self._diagrams:
                diagram.fill_graph(subgraph, namespace)
            for terminal in self._terminals:
                terminal.fill_graph(subgraph, namespace)

    def __str__(self):
        return type(self).__name__ + ":" + str(self._diagrams)

    __repr__ = __str__

class CaseStructure(Structure): pass

class LoopTest(TerminalClass):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)

class LoopCount(TerminalClass):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)


class Loop(Structure):
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        self._loopIndex = uuid_manager.node_to_object(node.findChild(LVheap.OBJ_FIELD_TAGS.OF__loopIndexDCO))
        self._loopTest = uuid_manager.node_to_object(node.findChild(LVheap.OBJ_FIELD_TAGS.OF__loopTestDCO))



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
    def __init__(self, uuid_manager, node):
        super().__init__(uuid_manager, node)
        self._nodes = []
        self._terminals = []
        self._signals = []

        nodelist = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__nodeList)
        for nodelist_item in iterate_direct_children(nodelist):
            if get_class_type(nodelist_item) == LVheap.SL_CLASS_TAGS.SL__sRN:
                terminals = nodelist_item.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
                for terminal in iterate_direct_children(terminals):
                    subnode = WeakNode(terminal)
                    if subnode:
                        self._terminals.append(subnode)

        zPlaneList = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__zPlaneList)
        for child_node in zPlaneList.childs:
            subnode = self.uuid_manager.node_to_object(child_node)
            if subnode:
                self._nodes.append(subnode)
        signallist = node.findChild(LVheap.OBJ_FIELD_TAGS.OF__signalList)
        for signal in iterate_direct_children(signallist):
            connected_terminals = signal.findChild(LVheap.OBJ_FIELD_TAGS.OF__termList)
            self._signals.append(Signal(self.uuid_manager, connected_terminals))

    def resolve_weak_nodes(self):
        super().resolve_weak_nodes()
        for index, node in enumerate(self._nodes):
            if isinstance(node, WeakNode):
                self._nodes[index] = self.uuid_manager.node_to_object(node._node)

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

def create_uuid_dict(heap):
    local_dict = {}
    for node in iterate_direct_children(heap):
        print(node)
        if get_class_type(node) != None and LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value in node.attribs:
            uuid = node.attribs[LVheap.SL_SYSTEM_ATTRIB_TAGS.SL__uid.value]
            local_dict[uuid] = node
        local_dict.update(create_uuid_dict(node))
    return local_dict


def get_dot_graph(file):
    vi_obj = vi.get_vi(file)
    uuids_to_nodes = {}
    block_diagram_root = None
    for block in vi_obj.blocks.values():
        block_identifier = bytearray(block.header.ident).decode()
        if 'BDH' in block_identifier:
            # print(block.sections)
            for index, section in block.sections.items():
                uuids_to_nodes.update(create_uuid_dict(section.objects[0]))
                root = section.objects[0].childs[0]
                block_diagram_root = root
        if "FPH" in block_identifier:
            for index, section in block.sections.items():
                uuids_to_nodes.update(create_uuid_dict(section.objects[0]))
                root = section.objects[0].childs[0]

    pprint(uuids_to_nodes)
    uuid_manager = UUIDManager(uuids_to_nodes)
    diagram = uuid_manager.node_to_object(block_diagram_root)
    # diagram.resolve_weak_nodes()
    print(diagram)
    g = graphviz.Digraph('G', engine='dot', format="svg", node_attr={"shape": "record"})
    diagram.fill_graph(g)
    pprint(uuid_manager._uuids_to_obj)
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
