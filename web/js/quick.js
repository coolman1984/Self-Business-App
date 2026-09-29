// A personal link opens a small page whose form is submitted here (not by the page itself), so that programs which only look
// at the link - chat previews, virus scanners - log nobody in.
const form = document.getElementById('go');
if (form) form.submit();
