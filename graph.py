import typing
from .notes import Note


class Graph:
    def __init__(self, nodes: typing.List[Note]):
        self.nodes = nodes
        self.graph = self.construct()

    def construct(self):
        root_node = Note()
        root_node._id = "root"
        graph = {root_node: []}
        for node in self.nodes:
            if node not in graph:
                graph[node] = []
            if node.parent:
                if node.parent in graph:
                    graph[node.parent].append(node)
                else:
                    graph[node.parent] = [node]
            else:
                graph[root_node].append(node)
        self.nodes.append(root_node)
        return graph

    def parent(self, node: Note) -> Note:
        for parent, children in self.graph.items():
            if node in children:
                return parent

    def children(self, node: Note) -> typing.List[Note]:
        return self.graph[node]

    def dfs(self) -> typing.List[Note]:
        output = []

        def process_node(node: Note):
            for child in self.children(node):
                output.append(child)
                process_node(child)

        root_node = [i for i in self.nodes if i._id == "root"][0]
        process_node(root_node)
        return output

    def __str__(self):
        return str(self.graph)

    def as_dot(self, orient_tag=True):
        output = "digraph {\n"
        for node in self.nodes:
            if node.as_dot(orient_tag):
                output += node.as_dot(orient_tag)
        output += "}"
        return output
