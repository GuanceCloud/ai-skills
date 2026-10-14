let page = 1;
document.querySelector('#next').addEventListener('click', () => {
  page += 1;
  history.pushState({}, '', `/?page=${page}&sort=price`);
  document.querySelector('#page').textContent = String(page);
  fetch(`/api/catalog?page=${page}&sort=price`);
});
