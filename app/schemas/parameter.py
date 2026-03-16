from pydantic import BaseModel


class ParameterSuggestionResponse(BaseModel):
    predefined_parameters: list[str]
    aliases: dict[str, list[str]]
