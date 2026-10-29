/**
 * MKCL COURSE SHOWCASE INTERACTIVE CONTROLLER
 * Handles Parent/Student Mode, Course Intro Modal, Slideshow Presentation,
 * Course Comparison, Career Quiz, and Admission Proposal Generator.
 */

(function () {
  'use strict';

  // Application State
  const state = {
    courses: window.MKCL_COURSES || window.COURSES_DATA || [],
    config: window.SHOWCASE_CONFIG || {},
    activeTrack: 'all',
    searchQuery: '',
    comparisonList: [], // max 3 course IDs
    currentIntroCourse: null,
    slideshow: {
      active: false,
      currentIndex: 0,
      autoPlayTimer: null,
      showNotes: true
    },
    quiz: {
      currentStep: 1,
      answers: {
        learnerType: null,
        interest: null,
        duration: null
      }
    }
  };

  // DOM Elements cache
  const elements = {
    recommendedSection: document.getElementById('recommendedSection'),
    recommendedGrid: document.getElementById('recommendedGrid'),
    coursesGrid: document.getElementById('coursesGrid'),
    resultsCount: document.getElementById('resultsCount'),
    searchInput: document.getElementById('courseSearchInput'),
    searchClearBtn: document.getElementById('searchClearBtn'),
    trackFilterBtns: document.querySelectorAll('.track-filter-pill'),
    
    // Modals
    introModal: document.getElementById('introModal'),
    introModalBody: document.getElementById('introModalBody'),
    compareModal: document.getElementById('compareModal'),
    compareModalBody: document.getElementById('compareModalBody'),
    compareFloatingBtn: document.getElementById('compareFloatingBtn'),
    compareCountBadge: document.getElementById('compareCountBadge'),
    quizModal: document.getElementById('quizModal'),
    quizModalBody: document.getElementById('quizModalBody'),
    proposalModal: document.getElementById('proposalModal'),
    proposalModalBody: document.getElementById('proposalModalBody'),
    
    // Slideshow
    slideshowOverlay: document.getElementById('slideshowOverlay'),
    slideshowStage: document.getElementById('slideshowStage'),
    slideCurrentNum: document.getElementById('slideCurrentNum'),
    slideTotalNum: document.getElementById('slideTotalNum'),
    slidePrevBtn: document.getElementById('slidePrevBtn'),
    slideNextBtn: document.getElementById('slideNextBtn'),
    slideshowCloseBtn: document.getElementById('slideshowCloseBtn'),
    toggleNotesBtn: document.getElementById('toggleNotesBtn'),
    launchSlideshowBtn: document.getElementById('launchSlideshowBtn'),
    launchQuizBtn: document.getElementById('launchQuizBtn')
  };

  // Initialize
  function init() {
    renderTrackCounts();
    renderRecommendedSection();
    renderCoursesGrid();
    setupEventListeners();
  }

  // Update track counts in pills
  function renderTrackCounts() {
    elements.trackFilterBtns.forEach(btn => {
      const trackId = btn.getAttribute('data-track');
      let count = 0;
      const published = state.courses.filter(c => c.is_published_web !== false);
      if (trackId === 'all') {
        count = published.length;
      } else {
        count = published.filter(c => c.track_id === trackId).length;
      }
      const countEl = btn.querySelector('.track-count');
      if (countEl) countEl.textContent = count;
    });
  }

  // Filter courses by track & search query
  function getFilteredCourses() {
    return state.courses.filter(course => {
      if (course.is_published_web === false) return false;
      const matchTrack = state.activeTrack === 'all' || course.track_id === state.activeTrack;
      if (!matchTrack) return false;
      
      if (!state.searchQuery) return true;
      const q = state.searchQuery.toLowerCase();
      return (
        course.title.toLowerCase().includes(q) ||
        course.category.toLowerCase().includes(q) ||
        course.summary.toLowerCase().includes(q) ||
        course.tools.some(t => t.toLowerCase().includes(q)) ||
        course.job_roles.some(j => j.toLowerCase().includes(q))
      );
    });
  }

  // Helper to build Unified Course Card HTML
  function renderCourseCardHtml(course, isRecommendedCard = false) {
    const isSelectedForCompare = state.comparisonList.includes(course.id);
    const isTrending = course.is_trending || (state.config.trending_course_ids && state.config.trending_course_ids.includes(course.id)) || course.id === 'ms-cit';
    
    let badgeClass = 'card-badge-floating';
    let badgeText = course.badge || 'Certified';

    if (isTrending) {
      badgeClass = 'card-badge-floating badge-trending';
      badgeText = '🔥 TRENDING';
    } else if (isRecommendedCard) {
      badgeClass = 'card-badge-floating badge-recommended';
      badgeText = '⭐ RECOMMENDED';
    }

    const topStudentPoint = (course.student_projects && course.student_projects[0]) || 'Hands-on practical training & portfolio projects.';
    const topParentPoint = (course.parent_points && course.parent_points[0]) || 'Recognized certification & strong employment stability.';
    const toolsHtml = (course.tools || []).slice(0, 4).map(t => `<span class="tool-tag">${t}</span>`).join('');

    return `
      <div class="course-card anim-fade-in-scale" style="--card-accent: ${course.accent};">
        <div class="card-top-accent"></div>
        <div class="card-media-wrapper">
          <img class="card-showcase-img" src="${course.showcase_image}" alt="${course.title}" loading="lazy" onerror="this.src='${course.thumbnail}'">
          <span class="${badgeClass}">${badgeText}</span>
          <span class="card-duration-floating">⏱ ${course.duration}</span>
        </div>
        <div class="card-body">
          <div class="card-category-label">${course.category}</div>
          <h3 class="card-title">${course.title}</h3>
          <p class="card-summary">${course.summary}</p>
          
          <div class="card-perspectives-dual">
            <div class="perspective-mini student-mini">
              <span class="perspective-mini-label">Student Focus:</span>
              <span class="perspective-mini-val">${topStudentPoint}</span>
            </div>
            <div class="perspective-mini parent-mini">
              <span class="perspective-mini-label">Parent Guidance:</span>
              <span class="perspective-mini-val">${topParentPoint}</span>
            </div>
          </div>

          <div class="card-tools-row">
            ${toolsHtml}
          </div>

          <div class="card-actions-row">
            <button class="btn-card-explore" data-action="explore" data-course-id="${course.id}">
              <span>Course Details</span>
              <span>➔</span>
            </button>
            <button class="btn-card-compare ${isSelectedForCompare ? 'selected' : ''}" data-action="compare" data-course-id="${course.id}" title="Add to comparison">
              <span>${isSelectedForCompare ? '✓ Added' : '+ Compare'}</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }

  // Render Recommended Courses Section
  function renderRecommendedSection() {
    if (!elements.recommendedGrid) return;
    
    const recConfigIds = (state.config && Array.isArray(state.config.recommended_course_ids))
      ? state.config.recommended_course_ids
      : ['ms-cit', 'tally-prime-with-gst', 'python', 'c-cpp-programming', 'graphic-designing', 'autocad'];

    const recCourses = state.courses.filter(c => {
      if (c.is_published_web === false) return false;
      return c.is_recommended || recConfigIds.includes(c.id);
    });

    if (recCourses.length === 0) {
      if (elements.recommendedSection) elements.recommendedSection.style.display = 'none';
      return;
    }

    if (elements.recommendedSection) elements.recommendedSection.style.display = 'block';
    elements.recommendedGrid.innerHTML = recCourses.map(c => renderCourseCardHtml(c, true)).join('');
  }

  // Render main course catalog grid
  function renderCoursesGrid() {
    const filtered = getFilteredCourses();
    
    if (elements.resultsCount) {
      elements.resultsCount.textContent = `Showing ${filtered.length} Career Programs`;
    }

    if (filtered.length === 0) {
      elements.coursesGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px;">
          <div style="font-size: 3rem; margin-bottom: 12px;">🔍</div>
          <h3 style="font-size: 1.3rem; color: #1E293B; margin-bottom: 8px;">No matching courses found</h3>
          <p style="color: #64748B; font-size: 0.95rem;">Try searching for another keyword or select a different track above.</p>
        </div>
      `;
      return;
    }

    elements.coursesGrid.innerHTML = filtered.map(c => renderCourseCardHtml(c, false)).join('');
  }

  // OPEN FULL-PAGE COURSE INTRO MODAL
  function openCourseIntro(courseId) {
    const course = state.courses.find(c => c.id === courseId);
    if (!course) return;
    state.currentIntroCourse = course;

    // Build Student Perspective
    const studentProjectsList = (course.student_projects || []).map(p => `<li>${p}</li>`).join('');
    const studentPanel = `
      <div class="perspective-display-box student-style" style="margin-bottom: 16px;">
        <h4 style="font-size: 1.1rem; color: #1D4ED8; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
          <span>🎓</span> Student Experience & Practical Projects
        </h4>
        <ul class="bullet-highlight-list">
          ${studentProjectsList}
        </ul>
        <div style="background: #EFF6FF; border: 1px solid #BFDBFE; padding: 10px 14px; border-radius: 8px; margin-top: 12px; font-size: 0.84rem; color: #1E40AF;">
          <strong>Practical Lab Focus:</strong> 100% hands-on exercises with modern software tools and portfolio creation.
        </div>
      </div>
    `;

    // Build Parent Guidance
    const parentPointsList = (course.parent_points || []).map(p => `<li>${p}</li>`).join('');
    const counselorTips = (course.counselor_talking_points || []).map(tip => `
      <div style="background: rgba(245, 158, 11, 0.08); border-left: 4px solid #F59E0B; padding: 10px 12px; border-radius: 8px; margin-top: 8px; font-size: 0.84rem; color: #92400E;">
        <strong>Counselor Guidance:</strong> ${tip}
      </div>
    `).join('');

    const parentPanel = `
      <div class="perspective-display-box parent-style">
        <h4 style="font-size: 1.1rem; color: #047857; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
          <span>👨‍👩‍👧</span> Parent Guidance & Career Value
        </h4>
        <ul class="bullet-highlight-list">
          ${parentPointsList}
        </ul>
        ${counselorTips}
      </div>
    `;

    // Tools Mastered chips
    const toolsChips = (course.tools || []).map(t => `
      <span style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; font-size: 0.85rem; font-weight: 700; color: #1E293B; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        ⚡ ${t}
      </span>
    `).join('');

    // Job Roles chips
    const jobRolesChips = (course.job_roles || []).map(r => `
      <span class="role-chip" style="display: inline-block; padding: 4px 10px; background: #F1F5F9; border-radius: 6px; font-size: 0.82rem; font-weight: 600; color: #334155; margin: 3px;">
        🎯 ${r}
      </span>
    `).join('');

    // Syllabus chips
    const syllabusChips = (course.syllabus || []).map((topic, i) => `
      <div class="syllabus-topic-chip">
        <span style="color: ${course.accent}; font-weight: 800; font-size: 0.75rem;">#${i + 1}</span>
        <span>${topic}</span>
      </div>
    `).join('');

    const isTrending = course.is_trending || (state.config.trending_course_ids && state.config.trending_course_ids.includes(course.id)) || course.id === 'ms-cit';
    const badgeText = isTrending ? '🔥 TRENDING' : (course.badge || 'Certified Program');

    // Bottom Recommended Courses Section
    const recConfigIds = (state.config && Array.isArray(state.config.recommended_course_ids))
      ? state.config.recommended_course_ids
      : ['ms-cit', 'tally-prime-with-gst', 'python', 'c-cpp-programming', 'graphic-designing', 'autocad'];

    const otherRecommended = state.courses.filter(c => 
      c.id !== course.id && 
      c.is_published_web !== false && 
      (c.is_recommended || recConfigIds.includes(c.id) || c.track_id === course.track_id)
    ).slice(0, 4);

    const otherRecCardsHtml = otherRecommended.map(rc => {
      const isTrendingRc = rc.is_trending || (state.config.trending_course_ids && state.config.trending_course_ids.includes(rc.id)) || rc.id === 'ms-cit';
      const badgeTextRc = isTrendingRc ? '🔥 TRENDING' : (rc.badge || 'Certified Program');
      return `
        <div class="related-rec-card" data-action="explore" data-course-id="${rc.id}">
          <img src="${rc.showcase_image}" alt="${rc.title}" class="related-rec-thumb" onerror="this.src='${rc.thumbnail}'">
          <div class="related-rec-info">
            <span class="related-rec-track">${rc.category}</span>
            <h4 class="related-rec-title">${rc.title}</h4>
            <p class="related-rec-desc">${rc.summary}</p>
            <div class="related-rec-footer">
              <span class="related-rec-duration">⏱ ${rc.duration}</span>
              <span class="related-rec-btn">View Details ➔</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    const bottomRecommendedSection = otherRecommended.length > 0 ? `
      <section class="details-bottom-recommended-section">
        <div class="details-rec-header">
          <span class="details-rec-kicker">⭐ Explore More Opportunities</span>
          <h3 class="details-rec-title">Recommended & Related Career Courses</h3>
          <p class="details-rec-subtitle">
            Complementary programs curated by Proff. Hemant Mahale to accelerate your professional career.
          </p>
        </div>
        <div class="details-rec-grid">
          ${otherRecCardsHtml}
        </div>
      </section>
    ` : '';

    elements.introModalBody.innerHTML = `
      <div class="intro-modal-hero" style="--modal-accent: ${course.accent};">
        <img class="intro-modal-bg-img" src="${course.showcase_image}" alt="${course.title}">
        <div class="intro-modal-hero-gradient"></div>
        <div class="intro-modal-hero-content">
          <div class="intro-badge-row">
            <span class="modal-track-badge">${course.category}</span>
            <span class="modal-stat-pill">⏱ ${course.duration}</span>
            <span class="modal-stat-pill">🎯 Level: ${course.level}</span>
            <span class="modal-stat-pill">🗣 ${course.language}</span>
          </div>
          <h2 class="intro-modal-title">${course.title}</h2>
          <p style="color: #E2E8F0; font-size: 1rem; max-width: 780px;">${badgeText}</p>
        </div>
      </div>

      <div class="modal-body-padding">
        <div class="modal-grid-2col">
          <!-- Left Column -->
          <div>
            <div class="card-intro-overview">
              <h3 class="modal-section-title">Course Overview</h3>
              <p>${course.summary}</p>
            </div>

            <!-- Concurrent Dual Perspectives for Students & Parents -->
            <div style="margin-bottom: 24px;">
              ${studentPanel}
              ${parentPanel}
            </div>

            <!-- Syllabus Explorer -->
            <div class="syllabus-explorer-box">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 class="modal-section-title" style="margin: 0;">📚 Comprehensive Syllabus (${(course.syllabus || []).length} Topics)</h3>
                <span style="font-size: 0.8rem; color: #64748B;">Work-Centric Practical Labs</span>
              </div>
              <input type="text" id="syllabusSearchInput" class="syllabus-search-input" placeholder="Search syllabus topics (e.g. GST, Python, Formulas, Drawing)...">
              <div class="syllabus-items-grid" id="syllabusGrid">
                ${syllabusChips}
              </div>
            </div>

            <!-- Tools & Software Mastered -->
            <div style="margin-top: 24px; margin-bottom: 24px;">
              <h3 class="modal-section-title">🛠️ Software & Tools Mastered</h3>
              <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                ${toolsChips}
              </div>
            </div>
          </div>

          <!-- Right Sidebar -->
          <div>
            <div class="modal-sidebar-card">
              <div class="sidebar-data-row">
                <div class="sidebar-label">Official Credibility</div>
                <div class="sidebar-value" style="color: #059669; font-size: 1.05rem;">
                  🏆 ${course.certificate}
                </div>
              </div>

              <div class="sidebar-data-row">
                <div class="sidebar-label">Eligibility Criteria</div>
                <div class="sidebar-value" style="font-size: 0.88rem; font-weight: 500; color: #334155;">
                  ${course.eligibility}
                </div>
              </div>

              <div class="sidebar-data-row">
                <div class="sidebar-label">Target Career Roles</div>
                <div class="job-roles-chips">
                  ${jobRolesChips}
                </div>
              </div>

              <div class="sidebar-data-row">
                <div class="sidebar-label">Estimated Entry Package</div>
                <div class="sidebar-value" style="color: #2563EB;">
                  💰 ${course.salary_range}
                </div>
              </div>
            </div>

            <!-- Counselor CTAs -->
            <div class="counselor-actions-stack">
              <button class="btn-counselor-action btn-generate-proposal" id="btnOpenProposal" data-course-id="${course.id}">
                <span>📄 Generate Admission Quote</span>
              </button>
              <button class="btn-counselor-action btn-whatsapp-inquiry" id="btnWhatsappShare" data-course-id="${course.id}">
                <span>💬 WhatsApp Inquiry Link</span>
              </button>
              <button class="btn-counselor-action" style="background: #F1F5F9; color: #334155; border: 1px solid #CBD5E1;" id="btnPresentSingleCourse" data-course-id="${course.id}">
                <span>📺 Present in Fullscreen</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      ${bottomRecommendedSection}
    `;

    elements.introModal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Scroll to top of full-window container
    const scrollContainer = elements.introModal.querySelector('.fullscreen-scroll-content') || elements.introModal;
    if (scrollContainer) scrollContainer.scrollTop = 0;

    // Syllabus search event
    const sylSearch = document.getElementById('syllabusSearchInput');
    const sylGrid = document.getElementById('syllabusGrid');
    if (sylSearch && sylGrid) {
      sylSearch.addEventListener('input', (e) => {
        const val = e.target.value.toLowerCase();
        const chips = sylGrid.querySelectorAll('.syllabus-topic-chip');
        chips.forEach(chip => {
          chip.style.display = chip.textContent.toLowerCase().includes(val) ? 'flex' : 'none';
        });
      });
    }

    // Modal internal perspective tabs
    const mParentTab = document.getElementById('modalParentTab');
    const mStudentTab = document.getElementById('modalStudentTab');
    if (mParentTab && mStudentTab) {
      mParentTab.addEventListener('click', () => {
        state.activeMode = 'parent';
        updateModeUI();
        openCourseIntro(course.id);
      });
      mStudentTab.addEventListener('click', () => {
        state.activeMode = 'student';
        updateModeUI();
        openCourseIntro(course.id);
      });
    }

    // Attach actions
    document.getElementById('btnOpenProposal')?.addEventListener('click', () => {
      openProposalModal(course.id);
    });
    document.getElementById('btnWhatsappShare')?.addEventListener('click', () => {
      generateWhatsAppLink(course);
    });
    document.getElementById('btnPresentSingleCourse')?.addEventListener('click', () => {
      closeAllModals();
      const idx = state.courses.findIndex(c => c.id === course.id);
      openSlideshow(idx !== -1 ? idx : 0);
    });
  }

  // CLOSE ALL MODALS
  function closeAllModals() {
    elements.introModal.classList.remove('active');
    elements.compareModal.classList.remove('active');
    elements.quizModal.classList.remove('active');
    elements.proposalModal.classList.remove('active');
    document.body.style.overflow = '';
  }

  // COMPARISON TOOL
  function toggleComparison(courseId) {
    const idx = state.comparisonList.indexOf(courseId);
    if (idx !== -1) {
      state.comparisonList.splice(idx, 1);
    } else {
      if (state.comparisonList.length >= 3) {
        alert("You can compare up to 3 courses at a time. Please remove one course to add another.");
        return;
      }
      state.comparisonList.push(courseId);
    }
    updateComparisonFloatingBar();
    renderCoursesGrid();
  }

  function updateComparisonFloatingBar() {
    const count = state.comparisonList.length;
    if (elements.compareCountBadge) {
      elements.compareCountBadge.textContent = count;
    }
    if (elements.compareFloatingBtn) {
      elements.compareFloatingBtn.style.display = count > 0 ? 'inline-flex' : 'none';
    }
  }

  function openComparisonModal() {
    if (state.comparisonList.length === 0) {
      alert("Please select at least 1 or 2 courses using '+ Compare' on the cards.");
      return;
    }

    const comparedCourses = state.courses.filter(c => state.comparisonList.includes(c.id));

    const headersHtml = comparedCourses.map(c => `
      <th style="min-width: 260px; text-align: center; border-top: 4px solid ${c.accent};">
        <h3 style="font-size: 1.15rem; color: #0F172A; margin-bottom: 4px;">${c.title}</h3>
        <span style="font-size: 0.75rem; color: ${c.accent}; font-weight: 800; text-transform: uppercase;">${c.category}</span>
      </th>
    `).join('');

    const durationHtml = comparedCourses.map(c => `<td>⏱ <strong>${c.duration}</strong></td>`).join('');
    const certHtml = comparedCourses.map(c => `<td style="color: #059669; font-weight: 700;">🏆 ${c.certificate}</td>`).join('');
    const toolsHtml = comparedCourses.map(c => `<td>${c.tools.map(t => `<span class="tool-tag" style="margin: 2px;">${t}</span>`).join('')}</td>`).join('');
    const jobsHtml = comparedCourses.map(c => `<td>${c.job_roles.slice(0, 4).join(', ')}</td>`).join('');
    const salaryHtml = comparedCourses.map(c => `<td style="color: #2563EB; font-weight: 700;">💰 ${c.salary_range}</td>`).join('');
    const parentPointsHtml = comparedCourses.map(c => `<td style="font-size: 0.85rem; color: #334155;">${c.parent_points[0]}</td>`).join('');
    const actionHtml = comparedCourses.map(c => `
      <td style="text-align: center;">
        <button class="btn-card-explore" onclick="window.MKCL_APP.openIntro('${c.id}')" style="background: ${c.accent}; width: 100%;">
          View Intro
        </button>
      </td>
    `).join('');

    elements.compareModalBody.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-size: 1.6rem; color: #0F172A;">⚖️ Course Comparison</h2>
        <button onclick="window.MKCL_APP.clearCompare()" style="color: #E11D48; font-size: 0.85rem; font-weight: 700;">Clear All</button>
      </div>
      <div class="comparison-table-wrapper">
        <table class="comparison-table">
          <thead>
            <tr>
              <th style="width: 180px;">Feature</th>
              ${headersHtml}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Duration</th>
              ${durationHtml}
            </tr>
            <tr>
              <th>Certification</th>
              ${certHtml}
            </tr>
            <tr>
              <th>Software Mastered</th>
              ${toolsHtml}
            </tr>
            <tr>
              <th>Career Roles</th>
              ${jobsHtml}
            </tr>
            <tr>
              <th>Package Range</th>
              ${salaryHtml}
            </tr>
            <tr>
              <th>Parent Key Benefit</th>
              ${parentPointsHtml}
            </tr>
            <tr>
              <th>Action</th>
              ${actionHtml}
            </tr>
          </tbody>
        </table>
      </div>
    `;

    elements.compareModal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  // FULLSCREEN SLIDESHOW PRESENTATION DECK
  function openSlideshow(startIndex = 0) {
    state.slideshow.active = true;
    state.slideshow.currentIndex = startIndex;
    elements.slideshowOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    renderSlide();
  }

  function renderSlide() {
    const list = getFilteredCourses();
    if (list.length === 0) return;
    
    // Bounds check
    if (state.slideshow.currentIndex < 0) state.slideshow.currentIndex = 0;
    if (state.slideshow.currentIndex >= list.length) state.slideshow.currentIndex = list.length - 1;

    const course = list[state.slideshow.currentIndex];
    elements.slideCurrentNum.textContent = state.slideshow.currentIndex + 1;
    elements.slideTotalNum.textContent = list.length;

    const parentHighlights = course.parent_points.slice(0, 3).map(p => `<li>${p}</li>`).join('');
    const studentProjects = course.student_projects.slice(0, 3).map(p => `<li>${p}</li>`).join('');

    elements.slideshowStage.innerHTML = `
      <div class="slide-content-card anim-fade-in-up" style="--card-accent: ${course.accent};">
        <div class="slide-left-col">
          <span class="slide-badge-category" style="background: ${course.accent}; color: #FFFFFF;">
            ${course.category}
          </span>
          <h2 class="slide-heading">${course.title}</h2>
          <p class="slide-summary-text">${course.summary}</p>

          <div class="slide-parent-box">
            <div class="slide-box-header">👨‍👩‍👦 Key Benefit for Parents & Students:</div>
            <ul style="list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 0.95rem; color: #E2E8F0;">
              ${state.activeMode === 'parent' ? parentHighlights : studentProjects}
            </ul>
          </div>

          <div style="display: flex; gap: 16px; margin-top: auto; font-size: 0.9rem; color: #94A3B8;">
            <span>⏱ <strong>Duration:</strong> ${course.duration}</span>
            <span>🏆 <strong>Certificate:</strong> ${course.certificate}</span>
            <span>💰 <strong>Package:</strong> ${course.salary_range}</span>
          </div>
        </div>

        <div class="slide-right-media">
          <img class="slide-main-img" src="${course.showcase_image}" alt="${course.title}" onerror="this.src='${course.thumbnail}'">
          <div class="slide-media-overlay-info">
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px;">
              ${course.tools.slice(0, 5).map(t => `<span class="tool-tag" style="background: rgba(255,255,255,0.9); color: #0F172A;">${t}</span>`).join('')}
            </div>
            <button class="btn-card-explore" onclick="window.MKCL_APP.openIntro('${course.id}')" style="background: ${course.accent}; width: 100%;">
              Open Deep-Dive Syllabus ➔
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function nextSlide() {
    const list = getFilteredCourses();
    if (state.slideshow.currentIndex < list.length - 1) {
      state.slideshow.currentIndex++;
      renderSlide();
    }
  }

  function prevSlide() {
    if (state.slideshow.currentIndex > 0) {
      state.slideshow.currentIndex--;
      renderSlide();
    }
  }

  function closeSlideshow() {
    state.slideshow.active = false;
    elements.slideshowOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  // CAREER COUNSELOR QUIZ (3 STEPS)
  function openQuizModal() {
    state.quiz.currentStep = 1;
    state.quiz.answers = { learnerType: null, interest: null, duration: null };
    renderQuizStep();
    elements.quizModal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function renderQuizStep() {
    if (state.quiz.currentStep === 1) {
      elements.quizModalBody.innerHTML = `
        <h2 style="font-size: 1.5rem; color: #0F172A; margin-bottom: 8px;">🎯 Step 1 of 3: Who is the Learner?</h2>
        <p style="color: #64748B; font-size: 0.95rem;">Select your current educational background or profile:</p>
        
        <div class="quiz-options-grid">
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('learnerType', 'school')">
            <span style="font-size: 1.6rem;">🎒</span>
            <div>
              <strong>School Student</strong>
              <div style="font-size: 0.75rem; color: #64748B;">5th to 10th Standard</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('learnerType', 'college')">
            <span style="font-size: 1.6rem;">🎓</span>
            <div>
              <strong>College Student</strong>
              <div style="font-size: 0.75rem; color: #64748B;">11th, 12th, or Degree</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('learnerType', 'jobseeker')">
            <span style="font-size: 1.6rem;">💼</span>
            <div>
              <strong>Job Seeker / Graduate</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Looking for immediate placement</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('learnerType', 'homemaker')">
            <span style="font-size: 1.6rem;">🏡</span>
            <div>
              <strong>Homemaker / Professional</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Self-development or work from home</div>
            </div>
          </button>
        </div>
      `;
    } else if (state.quiz.currentStep === 2) {
      elements.quizModalBody.innerHTML = `
        <h2 style="font-size: 1.5rem; color: #0F172A; margin-bottom: 8px;">🎯 Step 2 of 3: Primary Career Interest</h2>
        <p style="color: #64748B; font-size: 0.95rem;">What area excites the student most or aligns with your goals?</p>
        
        <div class="quiz-options-grid">
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('interest', 'govtit')">
            <span style="font-size: 1.6rem;">🏛️</span>
            <div>
              <strong>Govt Job & Core IT Literacy</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Mandatory MS-CIT certification</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('interest', 'finance')">
            <span style="font-size: 1.6rem;">📊</span>
            <div>
              <strong>Accounts & Finance</strong>
              <div style="font-size: 0.75rem; color: #64748B;">TallyPrime, GST, Advanced Excel</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('interest', 'design')">
            <span style="font-size: 1.6rem;">🎨</span>
            <div>
              <strong>Graphic Design & Media</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Photoshop, Video Editing, 3D</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('interest', 'coding')">
            <span style="font-size: 1.6rem;">💻</span>
            <div>
              <strong>Coding, Python & AI</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Programming, Web & AI/ML</div>
            </div>
          </button>
        </div>
      `;
    } else if (state.quiz.currentStep === 3) {
      elements.quizModalBody.innerHTML = `
        <h2 style="font-size: 1.5rem; color: #0F172A; margin-bottom: 8px;">🎯 Step 3 of 3: Preferred Duration</h2>
        <p style="color: #64748B; font-size: 0.95rem;">How much time can the student commit?</p>
        
        <div class="quiz-options-grid">
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('duration', 'fast')">
            <span style="font-size: 1.6rem;">⚡</span>
            <div>
              <strong>Fast-track (1 Month)</strong>
              <div style="font-size: 0.75rem; color: #64748B;">Intensive daily batches</div>
            </div>
          </button>
          <button class="quiz-option-btn" onclick="window.MKCL_APP.answerQuiz('duration', 'standard')">
            <span style="font-size: 1.6rem;">🗓️</span>
            <div>
              <strong>Standard (2-3 Months)</strong>
              <div style="font-size: 0.75rem; color: #64748B;">120-144 Hours with deep labs</div>
            </div>
          </button>
        </div>
      `;
    } else if (state.quiz.currentStep === 4) {
      // Calculate Recommendations
      renderQuizResults();
    }
  }

  function answerQuiz(key, value) {
    state.quiz.answers[key] = value;
    state.quiz.currentStep++;
    renderQuizStep();
  }

  function renderQuizResults() {
    const { learnerType, interest } = state.quiz.answers;
    let primarySlug = 'ms-cit';
    let comboName = 'Maharashtra Career Foundation Pack';
    let comboSlugs = ['ms-cit', 'office-assistance'];
    let comboDescription = 'MS-CIT + Back Office Executive: Mandatory Govt Job Qualification plus practical office computing.';
    let comboSavingText = 'Best Value: 2 Certifications in 3 Months';

    if (interest === 'govtit' || learnerType === 'school') {
      primarySlug = 'ms-cit';
      comboName = 'Digital Youth Foundation Pack';
      comboSlugs = ['ms-cit', 'english'];
      comboDescription = 'MS-CIT + Spoken English & Communication: Essential digital literacy with confident spoken English for school/college students.';
      comboSavingText = 'Career Fast-Track Combo';
    } else if (interest === 'finance' || (learnerType === 'college' && interest === 'finance')) {
      primarySlug = 'tally-prime-with-gst';
      comboName = 'Executive Corporate Accountant Pack';
      comboSlugs = ['tally-prime-with-gst', 'advanced-excel'];
      comboDescription = 'TallyPrime 4.0 with GST + Advanced Excel Dashboards: The most demanded qualification in accounting and corporate finance.';
      comboSavingText = 'High Earning Potential: ₹22,000 - ₹38,000 / month';
    } else if (interest === 'design') {
      primarySlug = 'graphic-designing';
      comboName = 'Commercial Creative Media Pack';
      comboSlugs = ['graphic-designing', 'autocad'];
      comboDescription = 'Graphic Designing (Photoshop/Illustrator) + AutoCAD 2D/3D: Prepare for creative agencies, architecture firms, and freelance design.';
      comboSavingText = 'Freelancing & Agency Ready';
    } else if (interest === 'coding') {
      primarySlug = 'python';
      comboName = 'Software Developer Master Pack';
      comboSlugs = ['python', 'c-cpp-programming'];
      comboDescription = 'Python Programming + C/C++ Engineering Logic: Solid algorithmic foundation and modern scripting for college projects and placement.';
      comboSavingText = 'Top Engineering & BCA Choice';
    }

    const primaryCourse = state.courses.find(c => c.id === primarySlug) || state.courses[0];
    const comboCourses = state.courses.filter(c => comboSlugs.includes(c.id));

    const comboTotalFee = comboCourses.reduce((sum, c) => sum + (c.base_fee || 4500), 0);
    const comboDiscountFee = Math.round(comboTotalFee * 0.9);

    elements.quizModalBody.innerHTML = `
      <div class="quiz-result-hero">
        <span class="section-kicker kicker-gold">CAREER PATHWAY ANALYSIS</span>
        <h2 style="font-size: 1.6rem; color: #0F172A; margin: 6px 0 8px;">Personalized Course Recommendation</h2>
        <p style="color: #64748B; font-size: 0.92rem; max-width: 620px; margin: 0 auto;">
          Grounded recommendations based on your educational background, employment demand, and MSBTE certification value.
        </p>
      </div>

      <!-- Top Direct Match -->
      <div class="quiz-match-box">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
          <div>
            <span style="font-size: 0.72rem; font-weight: 800; color: #059669; text-transform: uppercase; letter-spacing: 0.5px;">
              ★ 98% MATCH • TOP RECOMMENDATION
            </span>
            <h3 style="font-size: 1.3rem; color: #0F172A; margin: 4px 0;">${primaryCourse.title}</h3>
          </div>
          <span style="font-size: 0.85rem; font-weight: 700; color: #1E293B; background: #E2E8F0; padding: 4px 10px; border-radius: 8px;">
            ⏱ ${primaryCourse.duration}
          </span>
        </div>
        <p style="font-size: 0.88rem; color: #475569; margin-bottom: 12px; line-height: 1.5;">${primaryCourse.summary}</p>
        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #E2E8F0;">
          <div style="font-size: 0.84rem; color: #047857; font-weight: 700;">
            🏆 ${primaryCourse.certificate}
          </div>
          <button class="btn-card-explore" onclick="window.MKCL_APP.openIntro('${primaryCourse.id}')" style="background: ${primaryCourse.accent};">
            View Syllabus ➔
          </button>
        </div>
      </div>

      <!-- High-Value Center Combo Package -->
      <div class="combo-package-card">
        <div class="combo-header">
          <div>
            <span class="combo-pill">RECOMMENDED VALUE COMBO</span>
            <h4 style="font-size: 1.15rem; color: #312E81; margin-top: 4px;">${comboName}</h4>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.75rem; color: #6366F1; font-weight: 700;">Combo Package Fee</div>
            <div style="font-size: 1.2rem; font-weight: 800; color: #1E1B4B;">₹${comboDiscountFee.toLocaleString('en-IN')}</div>
          </div>
        </div>
        <p style="font-size: 0.86rem; color: #4338CA; line-height: 1.5; margin-bottom: 10px;">
          ${comboDescription}
        </p>
        <div style="font-size: 0.8rem; font-weight: 700; color: #047857; margin-bottom: 14px;">
          ✓ ${comboSavingText} • Dual Government/MKCL Certifications
        </div>
        
        <div class="combo-cta-row">
          <a class="btn-card-explore" href="https://wa.me/919271226772?text=Hello%20Proff%20Hemant%20Mahale%20Sir%2C%20I%20am%20interested%20in%20the%20${encodeURIComponent(comboName)}%20at%20Sudharm%20Infotech." target="_blank" style="background: #059669; text-align: center; flex: 1;">
            💬 WhatsApp Counselor (9271226772)
          </a>
          <button class="btn-header" onclick="window.MKCL_APP.openProposal('${primaryCourse.id}')" style="background: #FFFFFF; border-color: #CBD5E1; color: #1E293B; flex: 1;">
            📄 Generate Admission Proposal
          </button>
        </div>
      </div>

      <div style="text-align: center; margin-top: 16px;">
        <button class="btn-header" onclick="window.MKCL_APP.openQuiz()">Restart Counselor Quiz</button>
      </div>
    `;
  }

  // ADMISSION PROPOSAL / FEE QUOTE GENERATOR
  function openProposalModal(courseId) {
    const course = state.courses.find(c => c.id === courseId) || state.courses[0];
    
    const courseOptions = state.courses.map(c => `
      <option value="${c.id}" ${c.id === course.id ? 'selected' : ''}>${c.title} (${c.duration})</option>
    `).join('');

    elements.proposalModalBody.innerHTML = `
      <div class="no-print" style="margin-bottom: 24px;">
        <h2 style="font-size: 1.5rem; color: #0F172A; margin-bottom: 6px;">📄 Student Admission Proposal Generator</h2>
        <p style="color: #64748B; font-size: 0.9rem;">Fill in the student details to generate a professional, printable MKCL course proposal for parents:</p>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 16px;">
          <div>
            <label style="font-size: 0.75rem; font-weight: 700; color: #64748B;">Student Full Name:</label>
            <input type="text" id="propStudentName" value="Aditya Deshmukh" style="width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-family: inherit;">
          </div>
          <div>
            <label style="font-size: 0.75rem; font-weight: 700; color: #64748B;">Parent Phone / WhatsApp:</label>
            <input type="text" id="propParentPhone" value="+91 98765 43210" style="width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-family: inherit;">
          </div>
          <div>
            <label style="font-size: 0.75rem; font-weight: 700; color: #64748B;">Selected Course:</label>
            <select id="propCourseSelect" style="width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-family: inherit;">
              ${courseOptions}
            </select>
          </div>
          <div>
            <label style="font-size: 0.75rem; font-weight: 700; color: #64748B;">Preferred Batch Timing:</label>
            <select id="propBatchTime" style="width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 8px; font-family: inherit;">
              <option>Morning (08:00 AM - 10:00 AM)</option>
              <option>Morning (10:00 AM - 12:00 PM)</option>
              <option>Afternoon (02:00 PM - 04:00 PM)</option>
              <option selected>Evening (05:00 PM - 07:00 PM)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Printable Proposal Sheet -->
      <div class="proposal-sheet" id="printableProposalSheet">
        <div class="proposal-watermark">SUDHARM INFOTECH</div>
        
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #E2E8F0; padding-bottom: 20px; margin-bottom: 24px;">
          <div>
            <div style="font-size: 0.82rem; font-weight: 800; color: #E11D48; text-transform: uppercase; letter-spacing: 0.05em;">
              Sudharm Infotech
            </div>
            <h1 style="font-size: 1.6rem; color: #0F172A; margin: 4px 0;">Official Course Admission Proposal</h1>
            <p style="font-size: 0.85rem; color: #334155; font-weight: 600;">
              Teacher & Owner: <strong>Proff. Hemant Mahale</strong> &nbsp;|&nbsp; 📞 <strong>+91 9271226772</strong>
            </p>
            <p style="font-size: 0.78rem; color: #64748B;">MKCL Authorized Learning Center</p>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 0.85rem; font-weight: 700; color: #0F172A;">Date: ${new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
            <div style="font-size: 0.78rem; color: #64748B;">Ref: SUDHARM-${Math.floor(100000 + Math.random() * 900000)}</div>
          </div>
        </div>

        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px; margin-bottom: 24px;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
            <div>
              <span style="font-size: 0.72rem; color: #64748B; font-weight: 800; text-transform: uppercase;">Candidate Name</span>
              <div id="previewStudentName" style="font-size: 1.1rem; font-weight: 700; color: #0F172A;">Aditya Deshmukh</div>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: #64748B; font-weight: 800; text-transform: uppercase;">Contact Number</span>
              <div id="previewParentPhone" style="font-size: 1rem; font-weight: 600; color: #334155;">+91 98765 43210</div>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: #64748B; font-weight: 800; text-transform: uppercase;">Recommended Course</span>
              <div id="previewCourseTitle" style="font-size: 1.1rem; font-weight: 800; color: #E11D48;">${course.title}</div>
            </div>
            <div>
              <span style="font-size: 0.72rem; color: #64748B; font-weight: 800; text-transform: uppercase;">Batch Timing</span>
              <div id="previewBatchTime" style="font-size: 0.95rem; font-weight: 600; color: #334155;">Evening (05:00 PM - 07:00 PM)</div>
            </div>
          </div>
        </div>

        <div style="margin-bottom: 24px;">
          <h3 style="font-size: 1.1rem; color: #0F172A; margin-bottom: 10px;">📋 Course Highlights & Value:</h3>
          <ul style="list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 0.88rem; color: #334155;">
            <li>✔ <strong>Total Practical Lab Duration:</strong> ${course.duration}</li>
            <li>✔ <strong>Official Certification:</strong> ${course.certificate}</li>
            <li>✔ <strong>Software Taught:</strong> ${course.tools.join(', ')}</li>
            <li>✔ <strong>Target Industry Roles:</strong> ${course.job_roles.join(', ')}</li>
            <li>✔ <strong>Work-Centric Education:</strong> 100% practical hands-on labs with real case studies.</li>
          </ul>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: flex-end; padding-top: 24px; border-top: 1px dashed #CBD5E1; margin-bottom: 16px;">
          <div>
            <div style="font-size: 0.8rem; color: #64748B;">Teacher & Incharge</div>
            <div style="font-size: 1rem; font-weight: 800; color: #0F172A; margin-top: 2px;">Proff. Hemant Mahale</div>
            <div style="font-size: 0.78rem; color: #059669; font-weight: 600;">Owner, Sudharm Infotech • 9271226772</div>
          </div>
          <div style="text-align: right;">
            <div style="width: 160px; height: 50px; border-bottom: 1px solid #94A3B8; margin-left: auto;"></div>
            <div style="font-size: 0.8rem; color: #64748B; margin-top: 4px;">Sudharm Infotech Stamp & Sign</div>
          </div>
        </div>

        <div style="text-align: center; padding-top: 12px; border-top: 1px solid #E2E8F0; font-size: 0.75rem; color: #64748B; font-weight: 600;">
          ⚡ Powered by Arp Group Of Technology, Research & Developement
        </div>
      </div>

      <div class="no-print" style="margin-top: 24px; display: flex; justify-content: flex-end; gap: 12px;">
        <button class="btn-header" onclick="window.print()" style="background: #059669; color: #FFFFFF; border: none;">
          🖨️ Print / Save as PDF
        </button>
      </div>
    `;

    // Live update listeners
    document.getElementById('propStudentName')?.addEventListener('input', (e) => {
      document.getElementById('previewStudentName').textContent = e.target.value || 'Student Name';
    });
    document.getElementById('propParentPhone')?.addEventListener('input', (e) => {
      document.getElementById('previewParentPhone').textContent = e.target.value || 'Phone';
    });
    document.getElementById('propBatchTime')?.addEventListener('change', (e) => {
      document.getElementById('previewBatchTime').textContent = e.target.value;
    });
    document.getElementById('propCourseSelect')?.addEventListener('change', (e) => {
      const selected = state.courses.find(c => c.id === e.target.value);
      if (selected) {
        openProposalModal(selected.id);
      }
    });

    elements.proposalModal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  // WHATSAPP INQUIRY GENERATOR
  function generateWhatsAppLink(course) {
    const text = encodeURIComponent(
      `Hello Proff. Hemant Mahale Sir! I am inquiring about admission for "${course.title}" (${course.duration}) at Sudharm Infotech. Please share the batch timings and counselor meeting slot. Thank you!`
    );
    window.open(`https://api.whatsapp.com/send?phone=919271226772&text=${text}`, '_blank');
  }

  // EVENT LISTENERS
  function setupEventListeners() {
    // Mode toggles
    elements.parentModeBtn?.addEventListener('click', () => {
      state.activeMode = 'parent';
      updateModeUI();
    });
    elements.studentModeBtn?.addEventListener('click', () => {
      state.activeMode = 'student';
      updateModeUI();
    });

    // Track filter pills
    elements.trackFilterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        elements.trackFilterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.activeTrack = btn.getAttribute('data-track');
        renderCoursesGrid();
      });
    });

    // Search input
    elements.searchInput?.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.trim();
      elements.searchClearBtn.style.display = state.searchQuery ? 'flex' : 'none';
      renderCoursesGrid();
    });

    elements.searchClearBtn?.addEventListener('click', () => {
      elements.searchInput.value = '';
      state.searchQuery = '';
      elements.searchClearBtn.style.display = 'none';
      renderCoursesGrid();
    });

    // Global click delegation (handles catalog grid, recommended grid, and bottom recommended cards)
    document.addEventListener('click', (e) => {
      const exploreBtn = e.target.closest('[data-action="explore"]');
      if (exploreBtn) {
        const id = exploreBtn.getAttribute('data-course-id');
        if (id) {
          openCourseIntro(id);
        }
        return;
      }

      const compareBtn = e.target.closest('[data-action="compare"]');
      if (compareBtn) {
        const id = compareBtn.getAttribute('data-course-id');
        if (id) {
          toggleComparison(id);
        }
        return;
      }
    });

    // Modal Close buttons
    document.querySelectorAll('[data-action="close-modal"]').forEach(btn => {
      btn.addEventListener('click', closeAllModals);
    });

    // Close on overlay backdrop click
    document.querySelectorAll('.modal-overlay').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAllModals();
      });
    });

    // Slideshow controls
    elements.launchSlideshowBtn?.addEventListener('click', () => openSlideshow(0));
    elements.slideshowCloseBtn?.addEventListener('click', closeSlideshow);
    elements.slidePrevBtn?.addEventListener('click', prevSlide);
    elements.slideNextBtn?.addEventListener('click', nextSlide);

    // Quiz and Compare
    elements.launchQuizBtn?.addEventListener('click', openQuizModal);
    elements.compareFloatingBtn?.addEventListener('click', openComparisonModal);

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeAllModals();
        if (state.slideshow.active) closeSlideshow();
      }
      if (state.slideshow.active) {
        if (e.key === 'ArrowRight' || e.key === ' ') {
          nextSlide();
        } else if (e.key === 'ArrowLeft') {
          prevSlide();
        }
      }
    });
  }

  // Expose global methods for inline HTML onclick handlers
  window.MKCL_APP = {
    openIntro: openCourseIntro,
    openSlideshow: openSlideshow,
    openCompare: openComparisonModal,
    clearCompare: () => {
      state.comparisonList = [];
      updateComparisonFloatingBar();
      renderCoursesGrid();
      closeAllModals();
    },
    openQuiz: openQuizModal,
    answerQuiz: answerQuiz,
    openProposal: openProposalModal
  };

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
