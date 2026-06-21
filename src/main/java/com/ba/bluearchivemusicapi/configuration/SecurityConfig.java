package com.ba.bluearchivemusicapi.configuration;

import lombok.AllArgsConstructor;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.authorization.AuthorizationManager;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.intercept.RequestAuthorizationContext;
import org.springframework.util.StringUtils;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@AllArgsConstructor
@EnableConfigurationProperties({CorsProperties.class, AdminApiKeyProperties.class})
public class SecurityConfig {

    private static final String ADMIN_API_KEY_HEADER = "X-Admin-Api-Key";

    private final CorsProperties corsProperties;

    private final AdminApiKeyProperties adminApiKeyProperties;

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        return http
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/admin/**").access(adminApiKeyAuthorizationManager())
                        .anyRequest().permitAll()
                )
                .build();
    }

    private AuthorizationManager<RequestAuthorizationContext> adminApiKeyAuthorizationManager() {
        return (authentication, context) -> {
            String expectedApiKey = adminApiKeyProperties.apiKey();
            String actualApiKey = context.getRequest().getHeader(ADMIN_API_KEY_HEADER);
            boolean isAllowed = StringUtils.hasText(expectedApiKey) && expectedApiKey.equals(actualApiKey);
            return new AuthorizationDecision(isAllowed);
        };
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();

        config.setAllowedOrigins(corsProperties.allowedOrigins());
        config.setAllowedMethods(corsProperties.allowedMethods());
        config.setAllowedHeaders(corsProperties.allowedHeaders());
        config.setAllowCredentials(corsProperties.allowCredentials());

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
