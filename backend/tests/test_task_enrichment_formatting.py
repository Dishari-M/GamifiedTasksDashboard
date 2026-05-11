import unittest
from unittest.mock import Mock

from services import task_enrichment_service


class TaskEnrichmentFormattingTests(unittest.TestCase):
    def test_build_final_result_extracts_bold_rca_sections(self):
        codex_config = Mock()
        codex_config.extract_section.return_value = ""
        raw_output = """
**Root Cause**

`CORE_USER.MIDDLENAME` is saved, but the employee table path does not copy it.

**Affected Files**

- [EmployeeServiceFacadeImpl.java](C:/Oracle_Repo/myportal/employeeManagement/src/main/java/com/oracle/EmployeeServiceFacadeImpl.java:422) -> Add Employment Information copies employee data without middle name.
- Employee.java - Entity mapping should include the propagated middle name.

**Code Suggestion**

Set the middle name on the employee DTO before persisting.
"""

        result = task_enrichment_service._build_final_result(
            codex_config,
            "HRA-26819",
            {"title": "Middle name sync"},
            {"root_cause_analysis": raw_output, "tshirt_sizing": {"size": "XL", "reason": "Wide impact."}},
        )

        self.assertIn("employee table path", result["rca_reason"])
        self.assertEqual(len(result["affected_files"]), 2)
        self.assertEqual(result["affected_files"][0]["path"], "EmployeeServiceFacadeImpl.java")
        self.assertIn("Set the middle name", result["code_suggestion"])
        self.assertEqual(result["tshirt_size"], "XL")


if __name__ == "__main__":
    unittest.main()
