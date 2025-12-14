/* ========================================
   CHECKTRUTH LANDING PAGE JAVASCRIPT
   Smooth Scrolling, Animations, Mobile Menu
   ======================================== */

// ========== SMOOTH SCROLL NAVIGATION ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();

        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetElement = document.querySelector(targetId);

        if (targetElement) {
            // Close mobile menu if open
            const navMenu = document.getElementById('nav-menu');
            const navToggle = document.getElementById('nav-toggle');
            if (navMenu.classList.contains('active')) {
                navMenu.classList.remove('active');
                navToggle.classList.remove('active');
            }

            // Smooth scroll to target
            const navbarHeight = document.querySelector('.navbar').offsetHeight;
            const targetPosition = targetElement.offsetTop - navbarHeight;

            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });

            // Update active nav link
            updateActiveNavLink(targetId);
        }
    });
});

// ========== MOBILE MENU TOGGLE ==========
const navToggle = document.getElementById('nav-toggle');
const navMenu = document.getElementById('nav-menu');

if (navToggle) {
    navToggle.addEventListener('click', () => {
        navToggle.classList.toggle('active');
        navMenu.classList.toggle('active');
    });
}

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
    if (navMenu && navToggle) {
        if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
        }
    }
});

// ========== NAVBAR SCROLL EFFECT ==========
const navbar = document.getElementById('navbar');
let lastScrollTop = 0;

window.addEventListener('scroll', () => {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    // Add scrolled class when scrolling down
    if (scrollTop > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }

    lastScrollTop = scrollTop;
});

// ========== ACTIVE NAV LINK ON SCROLL ==========
function updateActiveNavLink(sectionId) {
    // Remove active class from all links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });

    // Add active class to current link
    const activeLink = document.querySelector(`.nav-link[href="${sectionId}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

// Update active nav link based on scroll position
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-link');

window.addEventListener('scroll', () => {
    let current = '';
    const scrollPosition = window.pageYOffset + 100;

    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;

        if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
            current = section.getAttribute('id');
        }
    });

    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${current}`) {
            link.classList.add('active');
        }
    });
});

// ========== SCROLL REVEAL ANIMATIONS ==========
function revealOnScroll() {
    const reveals = document.querySelectorAll('.benefit-card, .about-content, .stat-item');

    reveals.forEach(element => {
        const windowHeight = window.innerHeight;
        const elementTop = element.getBoundingClientRect().top;
        const elementVisible = 150;

        if (elementTop < windowHeight - elementVisible) {
            element.classList.add('reveal', 'active');
        }
    });
}

// Initial check
window.addEventListener('load', revealOnScroll);

// Check on scroll
window.addEventListener('scroll', revealOnScroll);

// ========== INTERSECTION OBSERVER FOR ANIMATIONS ==========
// More performant alternative to scroll event for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('reveal', 'active');
            // Optional: stop observing after animation
            // observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all benefit cards and sections
document.addEventListener('DOMContentLoaded', () => {
    const elementsToAnimate = document.querySelectorAll('.benefit-card, .stat-item');
    elementsToAnimate.forEach(element => {
        element.classList.add('reveal');
        observer.observe(element);
    });
});

// ========== DYNAMIC YEAR IN FOOTER ==========
const currentYear = new Date().getFullYear();
const footerYear = document.querySelector('.footer-bottom p');
if (footerYear) {
    footerYear.textContent = `© ${currentYear} CheckTruth. All rights reserved.`;
}

// ========== PRELOAD CRITICAL IMAGES ==========
// Preload hero image for better performance
window.addEventListener('load', () => {
    const heroImage = document.querySelector('.mockup-img');
    if (heroImage && !heroImage.complete) {
        heroImage.style.opacity = '0';
        heroImage.addEventListener('load', () => {
            heroImage.style.transition = 'opacity 0.5s ease-in';
            heroImage.style.opacity = '1';
        });
    }
});

// ========== PERFORMANCE: DEBOUNCE SCROLL EVENTS ==========
function debounce(func, wait = 10, immediate = true) {
    let timeout;
    return function () {
        const context = this;
        const args = arguments;
        const later = function () {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// Apply debounce to scroll-heavy functions
window.addEventListener('scroll', debounce(() => {
    // Any additional scroll-based logic can go here
}, 15));

// ========== ACCESSIBILITY: FOCUS MANAGEMENT ==========
// Ensure keyboard navigation works properly
document.addEventListener('keydown', (e) => {
    // Close mobile menu on Escape key
    if (e.key === 'Escape' && navMenu.classList.contains('active')) {
        navMenu.classList.remove('active');
        navToggle.classList.remove('active');
    }
});

// ========== SMOOTH PAGE LOAD ==========
window.addEventListener('load', () => {
    document.body.classList.add('loaded');

    // Trigger initial animations
    setTimeout(() => {
        revealOnScroll();
    }, 100);
});

// ========== CONSOLE MESSAGE ==========
console.log('%c🌿 CheckTruth Landing Page', 'color: #10b981; font-size: 20px; font-weight: bold;');
console.log('%cKnow What You Eat. Choose What\'s Right.', 'color: #059669; font-size: 14px;');
