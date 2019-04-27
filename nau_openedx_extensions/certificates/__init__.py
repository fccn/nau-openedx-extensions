"""

TODO: make this docstring way better


Crude example of reading in the cert

<h1>${ context.get("new_key", "This one should exist") }</h1>
<h1>${ context.get("fake_key", "A fake key renders a default") }</h1>
<h1>${ safe(fake_key)  }</h1>


A function to make the reading safer
<%def name="safe(value)">
    % if value is UNDEFINED:
      <!-- UNDEFINED value. Caught by the "safe" function-->
    % else:
      ${ value }
    % endif
</%def>

"""


def update_cert_context(context, request, course, user, user_certificate, configuration, *args, **kwargs):
    """
    """
    context.update({"users_real_name": "new_value"})
