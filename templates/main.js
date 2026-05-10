// 1. Récupérer le panier depuis le stockage local (ou créer un tableau vide)
let cart = JSON.parse(localStorage.getItem('floral_cart')) || [];

// 2. Mettre à jour le compteur du panier dans la barre de navigation
function updateCartCount() {
    const countElement = document.getElementById('cart-count');
    if (countElement) {
        countElement.innerText = cart.length;
    }
}

// 3. Sauvegarder le panier dans la mémoire du navigateur
function saveCart() {
    localStorage.setItem('floral_cart', JSON.stringify(cart));
    updateCartCount();
}

// 4. Ajouter au panier depuis la page d'accueil
document.querySelectorAll('.add-to-cart').forEach(button => {
    button.addEventListener('click', (e) => {
        const name = e.target.getAttribute('data-name');
        const price = parseFloat(e.target.getAttribute('data-price'));
        
        cart.push({ name, price });
        saveCart();
        alert(`${name} ajouté au panier !`);
    });
});

// 5. Afficher le panier sur la page cart.html
const cartItemsElement = document.getElementById('cart-items');
if (cartItemsElement) {
    let total = 0;
    cartItemsElement.innerHTML = '';
    cart.forEach((item, index) => {
        const li = document.createElement('li');
        li.innerHTML = `${item.name} - ${item.price}$ <button onclick="removeFromCart(${index})" style="margin-left: 10px; color: red;">X</button>`;
        cartItemsElement.appendChild(li);
        total += item.price;
    });
    document.getElementById('cart-total').innerText = total;
}

// Fonction pour supprimer un élément du panier
window.removeFromCart = function(index) {
    cart.splice(index, 1);
    saveCart();
    window.location.reload(); // Recharger la page pour mettre à jour la liste
};

// 6. Remplir le total sur la page checkout.html
const payTotalElement = document.getElementById('pay-total');
if (payTotalElement) {
    let total = 0;
    cart.forEach(item => total += item.price);
    payTotalElement.innerText = total;
}

// Appel de base pour initialiser le compteur
updateCartCount();
