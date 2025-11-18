const availabilityList = document.getElementById("availability-list");
const btnAdd = document.getElementById("btn-add-availability");
const form = document.getElementById("planner-form");
const statusEl = document.getElementById("status");

function createAvailabilityRow() {
  const div = document.createElement("div");
  div.className = "availability-row";

  const dateInput = document.createElement("input");
  dateInput.type = "date";
  dateInput.required = true;

  const startInput = document.createElement("input");
  startInput.type = "time";
  startInput.required = true;

  const endInput = document.createElement("input");
  endInput.type = "time";
  endInput.required = true;

  const delBtn = document.createElement("button");
  delBtn.type = "button";
  delBtn.className = "btn btn-danger";
  delBtn.textContent = "削除";
  delBtn.addEventListener("click", () => {
    availabilityList.removeChild(div);
  });

  div.appendChild(dateInput);
  div.appendChild(startInput);
  div.appendChild(endInput);
  div.appendChild(delBtn);

  return div;
}

btnAdd.addEventListener("click", () => {
  const row = createAvailabilityRow();
  availabilityList.appendChild(row);
});

// 最初から1行は出しておく
availabilityList.appendChild(createAvailabilityRow());

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  statusEl.textContent = "";
  statusEl.className = "status";

  const name = document.getElementById("name").value.trim();
  const area = document.getElementById("area").value.trim();
  const foodDislike = document.getElementById("food-dislike").value.trim();
  const foodWeak = document.getElementById("food-weak").value.trim();
  const foodCant = document.getElementById("food-cant").value.trim();
  const foodWant = document.getElementById("food-want").value.trim();

  const rows = Array.from(
    availabilityList.querySelectorAll(".availability-row")
  );

  const availabilities = [];
  for (const row of rows) {
    const [dateInput, startInput, endInput] = row.querySelectorAll("input");
    if (!dateInput.value || !startInput.value || !endInput.value) {
      continue;
    }
    availabilities.push({
      date: dateInput.value,
      start: startInput.value,
      end: endInput.value,
    });
  }

  if (!availabilities.length) {
    statusEl.textContent = "空いている日・時間を少なくとも1つ入力してください。";
    statusEl.classList.add("err");
    return;
  }

  const payload = {
    name,
    area,
    availabilities,
    food_dislike: foodDislike,
    food_weak: foodWeak,
    food_cant: foodCant,
    food_want: foodWant,
  };

  try {
    statusEl.textContent = "送信中...";
    const res = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "送信に失敗しました。");
    }

    statusEl.textContent = "送信しました。ありがとうございます！";
    statusEl.classList.add("ok");
    form.reset();
    // 空き日行をリセット
    availabilityList.innerHTML = "";
    availabilityList.appendChild(createAvailabilityRow());
  } catch (err) {
    console.error(err);
    statusEl.textContent = err.message || "エラーが発生しました。";
    statusEl.classList.add("err");
  }
});
