document.addEventListener("DOMContentLoaded", () => {
  const answer = document.getElementById("answer");
  const count = document.getElementById("char-count");
  if (answer && count) {
    const update = () => { count.textContent = `${answer.value.length.toLocaleString()} / 10,000`; };
    answer.addEventListener("input", update);
    update();
    answer.focus();
  }
});
