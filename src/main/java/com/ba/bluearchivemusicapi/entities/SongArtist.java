package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "song_artist")
@IdClass(SongArtistId.class)
public class SongArtist {

    @Id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "song_id")
    private Song song;

    @Id
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "artist_id")
    private Artist artist;

    @Id
    @Enumerated(EnumType.STRING)
    @Column(name = "type")
    private SongArtistType type;

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;
}

