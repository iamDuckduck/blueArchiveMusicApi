package com.ba.bluearchivemusicapi.entities;


import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;
import java.util.LinkedHashSet;
import java.util.Set;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@EntityListeners(AuditingEntityListener.class)
@Table(name = "artist")
public class Artist {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 255)
    private String name;

    @Column(name = "character_name", length = 255)
    private String characterName;

    @Column(name = "voice_actor_name", length = 255)
    private String voiceActorName;

    @ElementCollection
    @CollectionTable(name = "artist_alias", joinColumns = @JoinColumn(name = "artist_id"))
    @Column(name = "alias", nullable = false, length = 255)
    @Builder.Default
    private Set<String> aliases = new LinkedHashSet<>();

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;

    @LastModifiedDate
    @Column(name = "updated_date")
    private LocalDate updatedDate;
}
