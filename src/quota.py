from dataclasses import dataclass


@dataclass
class Quota:
    name: str
    percent: int
    reset_text: str = ""

    def status(self):
        if self.percent >= 70:
            return "充足"
        if self.percent >= 20:
            return "正常"
        return "紧张"
