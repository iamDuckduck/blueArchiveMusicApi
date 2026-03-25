package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@EntityListeners(AuditingEntityListener.class)
@Table(name = "song")
public class Song {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title")
    private String title;

    @Column(name = "image_path")
    private String imagePath;

    @Column(name = "audio_path")
    private String audioPath;

    @Column(name = "description")
    private String description;

    @Column(name = "play_count")
    private Long playCount;

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;

    @LastModifiedDate
    @Column(name = "updated_date")
    private LocalDate updatedDate;

    @ManyToOne
    @JoinColumn(name = "album_id")
    private Album album;

    @OneToMany(mappedBy = "song", cascade = CascadeType.PERSIST)
    @Builder.Default
    private List<SongArtist> songArtists = new ArrayList<>();

    // ──── Helper methods ────

    public List<Artist> getArtists() {
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.ARTIST)
                .map(SongArtist::getArtist)
                .collect(Collectors.toList());
    }

    public List<Artist> getComposers() {
        return songArtists.stream()
                .filter(sa -> sa.getType() == SongArtistType.COMPOSER)
                .map(SongArtist::getArtist)
                .collect(Collectors.toList());
    }

    public void addArtist(Artist artist, SongArtistType type) {
        SongArtist sa = SongArtist.builder()
                .song(this)
                .artist(artist)
                .type(type)
                .build();
        songArtists.add(sa);
    }
}
