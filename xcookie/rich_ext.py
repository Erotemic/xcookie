from rich import prompt
import ubelt as ub


class FuzzyPrompt(prompt.Prompt):
    """
    The user just needs to enter a non-ambiguous prefix
    """
    def process_response(self, value: str) -> str:
        """Normalize the response"""
        assert self.choices is not None
        got = value.strip().lower()
        norm_choices = [c.lower() for c in self.choices]
        flags = [c.startswith(got) for c in norm_choices]
        if sum(flags) != 1:
            raise prompt.InvalidResponse(self.validate_error_message)
        norm = ub.peek(ub.compress(self.choices, flags))
        return norm
