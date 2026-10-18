"""Pure helpers for OpenFlow message handling."""


def has_usable_buffer_id(buffer_id, no_buffer_id):
    """Return whether a switch-owned packet buffer can be referenced safely."""
    return buffer_id is not None and buffer_id != no_buffer_id
