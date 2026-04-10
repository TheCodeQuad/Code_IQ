import React from 'react';

const CardNav = ({
  logo,
  logoAlt = 'Logo',
  middleContent,
  rightContent,
  className = '',
  baseColor = '#fff',
  buttonBgColor,
  buttonTextColor,
  buttonText = 'Get Started',
  onButtonClick
}: any) => {
  return (
    <div
      className={`card-nav-container absolute left-1/2 -translate-x-1/2 w-[90%] max-w-[1200px] z-[99] top-[1.2em] md:top-[2em] ${className}`}
    >
      <nav
        className={`card-nav block h-[60px] p-0 rounded-xl shadow-md relative`}
        style={{ backgroundColor: baseColor }}
      >
        <div className="h-[60px] flex items-center justify-between p-2 pl-4">
          <div className="logo-container flex items-center flex-shrink-0">
            {typeof logo === 'string' ? (
              <img src={logo} alt={logoAlt} className="logo h-[28px]" />
            ) : (
              logo
            )}
          </div>

          <div className="hidden lg:flex items-center justify-center flex-1 gap-1 px-4">
            {middleContent}
          </div>

          <div className="flex items-center gap-2 pr-2 flex-shrink-0">
            {rightContent}
            {buttonText && (
              <button
                type="button"
                onClick={onButtonClick}
                className="card-nav-cta-button items-center h-full py-2 px-4 rounded-[calc(0.75rem-0.2rem)] font-medium cursor-pointer transition-colors duration-300 gap-2 flex"
                style={{ backgroundColor: buttonBgColor, color: buttonTextColor }}
              >
                {buttonText}
              </button>
            )}
          </div>
        </div>
      </nav>
    </div>
  );
};

export default CardNav;