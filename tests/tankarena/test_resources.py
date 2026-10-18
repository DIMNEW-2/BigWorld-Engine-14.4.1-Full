import ast
import os
import xml.etree.ElementTree as ET
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESOURCE_ROOT = os.path.join(ROOT, "game", "res", "tankarena")
SCRIPTS_ROOT = os.path.join(RESOURCE_ROOT, "scripts")


class ResourceWiringTests(unittest.TestCase):
    def test_resource_xml_is_well_formed(self):
        for directory, unused_dirs, filenames in os.walk(RESOURCE_ROOT):
            for filename in filenames:
                if filename.endswith((".xml", ".def")):
                    path = os.path.join(directory, filename)
                    with self.subTest(path=os.path.relpath(path, ROOT)):
                        ET.parse(path)

    def test_unknown_accounts_use_player_proxy_and_start_service(self):
        bw = ET.parse(os.path.join(RESOURCE_ROOT, "server", "bw.xml")).getroot()
        self.assertEqual(
            bw.findtext("./billingSystem/entityTypeForUnknownUsers").strip(),
            "TankPlayer")
        self.assertEqual(
            bw.findtext("./personality").strip(), "TankArena")

        entities = ET.parse(os.path.join(SCRIPTS_ROOT, "entities.xml")).getroot()
        self.assertIsNotNone(entities.find("./ClientServerEntities/TankPlayer"))
        services = ET.parse(os.path.join(SCRIPTS_ROOT, "services.xml")).getroot()
        self.assertIsNotNone(services.find("./OfflineBattleService"))

    def test_declared_player_methods_exist_in_base_script(self):
        definition = ET.parse(
            os.path.join(SCRIPTS_ROOT, "entity_defs", "TankPlayer.def")).getroot()
        methods = [node.tag for node in definition.findall("./BaseMethods/*")]
        path = os.path.join(SCRIPTS_ROOT, "base", "TankPlayer.py")
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        class_node = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == "TankPlayer")
        python_methods = {node.name for node in class_node.body
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertTrue(set(methods).issubset(python_methods))

    def test_service_definition_methods_exist_in_service_script(self):
        definition = ET.parse(
            os.path.join(SCRIPTS_ROOT, "service_defs", "OfflineBattleService.def")).getroot()
        methods = [node.tag for node in definition.findall("./Methods/*")]
        path = os.path.join(SCRIPTS_ROOT, "service", "OfflineBattleService.py")
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        class_node = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and
                          node.name == "OfflineBattleService")
        python_methods = {node.name for node in class_node.body
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertTrue(set(methods).issubset(python_methods))


if __name__ == "__main__":
    unittest.main()
