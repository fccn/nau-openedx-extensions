function sendMessage(form) {
  var targets = [];
  var jForm = $(form);
  var body = form.message.value;
  var sendTo = jForm.find("input[name='send_to']");
  var messageApiEndpoint = jForm.find("input[type='submit']").data("endpoint");

  sendTo.filter(":checked").each(function () {
    return targets.push(this.value);
  });
  if (body === "") {
    return alert(gettext("Your message cannot be blank."));
  }
  if (targets.length === 0) {
    return alert(gettext("Your message must have at least one target."));
  }

  var confirmMessage = gettext("You are sending a new message. Is this OK?");
  if (confirm(confirmMessage)) {
    sendData = {
      action: "send",
      send_to: JSON.stringify(targets),
      message: body,
    };
    return $.ajax({
      type: "POST",
      dataType: "json",
      url: messageApiEndpoint,
      data: sendData,
      success: function () {
        return display_response(
          gettext(
            "Your message was successfully queued for sending. In courses with a large number of learners, messages to learners might take some time to be sent."
          ),
          jForm
        );
      },
      error: function () {
        return fail_with_error(gettext("Error sending message."), jForm);
      },
    });
  }
}

function fail_with_error(msg, form) {
  var $request_response = form.find(".request-response");
  var $request_response_error = form.find(".request-response-error");
  $request_response.empty();
  $request_response_error.empty();
  $request_response_error.text(msg);
  return form.find(".msg-confirm").css({
    display: "none",
  });
}

function display_response(msg, form) {
  var $request_response = form.find(".request-response");
  $request_response.empty();
  var $request_response_error = form.find(".request-response-error");
  $request_response_error.empty();
  $request_response.text(msg);
  return form.find(".msg-confirm").css({
    display: "block",
  });
}

