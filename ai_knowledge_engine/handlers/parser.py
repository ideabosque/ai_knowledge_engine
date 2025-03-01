import json, csv, re
from typing import Any, Dict

class Parser:
    def __init__(self):
        self.csv_delimiters = [",",";","\t","|"]
        self.json_leading_count = 0 
        self.json_leading_trailing = 0
        self.data_room = ""
        self.need_read_next = False

    def parse(self:Any, header:str, data:str) -> Dict[str, Any]:
        result = self._parse_json(data)

        if type(result) is dict:
            return result
        elif self.need_read_next:
            return None
        return self._parse_csv(header, data)
    def _parse_json(self:Any, data:str) -> Dict[str, Any]:
        """
        Check if it is Json format data and try to parse it
        """
        data = str(data).strip()
        pattern = r'^\s*(\{|\[).*(\}|\])\s*$|^\s*(\{|\[).*|.*(\}|\])\s*$'

        if bool(re.match(pattern, data)):
            self.data_room += data
            self.json_leading_count += data.count("{")
            self.json_leading_trailing += data.count("}")
            self.need_read_next = True

            if self.json_leading_count == self.json_leading_trailing:
                try:
                    obj = json.loads(self.data_room)
                    self.data_room = ""
                    self.json_leading_count = 0
                    self.json_leading_trailing = 0
                    self.need_read_next = False
                    return obj
                except json.JSONDecodeError:
                    pass
        return None
        
    def _parse_csv(self:Any, header: str, data: str) -> Dict[str, Any]:
        header = str(header)
        data = str(data)

        if header == "":
            return None

        try:
            headers = next(csv.reader([header]))

            for k, v in enumerate(headers):
               # TODO: More complex scenarios need to be considered
               headers[k] = v.replace(" ", "_").lower().strip()

            return dict(zip(headers, next(csv.reader([data]))))
        except ValueError:
            return None

    def camel_to_snake(self, text:str) -> str:
        """
        Convert camel case to snake case
        """
        text = re.sub(r'(?<!^)(?=[A-Z])', '_', text).lower()

        if text[0] == "_":
            text = text[1:]

        return text